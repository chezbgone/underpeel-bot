from decimal import Decimal
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Self

from database import the_table

LOG = logging.getLogger(__name__)

"""
SCHEMA:
=======
userid, robomoji#update#{timestamp} : {
    staff_id: int | Literal['SYSTEM']
    emoji: int
    added : bool
    reason : str
}

userid, robomoji#info : {
    emojis: list[binary]
    last_reacted: optional[datetime]
}
"""

def _make_sk(*layers: str) -> str:
    _sk_prefix = 'robomoji'
    _sk_separator = '#'
    return _sk_separator.join((_sk_prefix, *layers))

def _make_key(user_id: int, *layers: str):
    return {
        'id': user_id,
        'sk': _make_sk(*layers)
    }

_update_prefix = 'update'

@dataclass
class RobomojiTransaction:
    time: datetime
    staff: int | Literal['SYSTEM']
    chatter_id: int
    action: Literal['added', 'removed']
    emoji: str
    reason: str

    @classmethod
    def parse(cls, item) -> Self:
        assert('sk' in item)
        match = re.fullmatch(f'robomoji#{_update_prefix}#(?P<timestamp>.*)', item['sk'])
        assert(match is not None)
        timestamp = datetime.fromisoformat(match['timestamp'])

        assert('staff_id' in item)
        if (staff_id := item['staff_id']) != 'SYSTEM':
            assert(type(staff_id) is Decimal)
            staff_id = int(staff_id)

        assert('id' in item)
        assert(type(item['id']) is Decimal)
        chatter_id = int(item['id'])

        assert('added' in item)
        assert(type(item['added']) is bool)
        action = 'added' if item['added'] else 'removed'

        assert('emoji' in item)
        emoji = bytes(item['emoji']).decode()

        assert('reason' in item)
        reason = item['reason']

        return cls(timestamp, staff_id, chatter_id, action, emoji, reason)

def get_emoji_changes(user_id: int, limit=15) -> list[RobomojiTransaction]:
    response = the_table().query(
        KeyConditionExpression='id = :id AND begins_with(sk, :sk_prefix)',
        ExpressionAttributeValues={
            ':id': user_id,
            ':sk_prefix': _make_sk(_update_prefix),
        },
        ScanIndexForward=False,
        Limit=limit,
    )
    changes = response.get('Items', []) # type: ignore

    return [
        RobomojiTransaction.parse(item)
        for item in changes
    ]

def get_emoji_info(user_id: int) -> tuple[datetime | None, list[str]]:
    response = the_table().get_item(
        Key=_make_key(user_id, 'info'),
        ProjectionExpression='emojis, last_reacted'
    )
    last_reacted_raw: str | None = response.get('Item', {}).get('last_reacted')  # type: ignore
    emojis_raw: set[SupportsBytes] = response.get('Item', {}).get('emojis', set())  # type: ignore

    last_reacted = None
    if last_reacted_raw is not None:
        last_reacted = datetime.fromisoformat(last_reacted_raw)

    emojis = [bytes(emoji).decode() for emoji in emojis_raw]

    return last_reacted, emojis

def register_emoji_use(user_id: int):
    the_table().update_item(
        Key=_make_key(user_id, 'info'),
        UpdateExpression='SET last_reacted = :t',
        ExpressionAttributeValues={
            ':t': datetime.now().isoformat(),
        },
    )

def toggle_emoji(
    staff_id: int | Literal['SYSTEM'],
    user_id: int,
    emoji: str,
    reason: str,
) -> Literal['added', 'removed']:
    _, user_emojis = get_emoji_info(user_id)
    operation = 'removed' if emoji in user_emojis else 'added'

    the_table().put_item(
        Item={
            **_make_key(user_id, _update_prefix, datetime.now().isoformat()),
            'staff_id': staff_id,
            'emoji': emoji.encode(),
            'added': operation == 'added',
            'reason': reason
        }
    )
    if operation == 'removed':
        i = user_emojis.index(emoji)
        # can't factor .update_item out because
        # ExpressionAttributeValues can't be empty dict
        the_table().update_item(
            Key=_make_key(user_id, 'info'),
            UpdateExpression=f"REMOVE emojis[{i}]"
        )
    else:
        the_table().update_item(
            Key=_make_key(user_id, 'info'),
            UpdateExpression="SET emojis = list_append(if_not_exists(emojis, :empty), :emoji)",
            ExpressionAttributeValues= {
                # unicode string emojis get messed up in transit
                ':emoji': [emoji.encode()],
                ':empty': [],
            }
        )
    return operation
