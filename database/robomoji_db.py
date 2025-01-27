import logging
import re
from datetime import datetime
from typing import Literal

from database import the_table
from models.robomoji import RobomojiTransaction

LOG = logging.getLogger(__name__)

"""
SCHEMA:
=======
user#{userid}, robomoji#update#{timestamp} : {
    staff_id: int | Literal['SYSTEM']
    emoji: int
    added : bool
    reason : str
}

user#{userid}, robomoji#info : {
    emojis: list[binary]
    last_reacted: optional[datetime]
}
"""

def _make_id(user_id: int) -> str:
    return f'user#{user_id}'

def _make_sk(*layers: str) -> str:
    _sk_prefix = 'robomoji'
    _sk_separator = '#'
    return _sk_separator.join((_sk_prefix, *layers))

def _make_key(user_id: int, *layers: str):
    return {
        'id': _make_id(user_id),
        'sk': _make_sk(*layers)
    }

_update_prefix = 'update'

def get_emoji_changes(user_id: int, limit=15) -> list[RobomojiTransaction]:
    def make_robomoji_transaction(item):
        assert('sk' in item)
        match = re.fullmatch(f'robomoji#{_update_prefix}#(?P<timestamp>.*)', item['sk'])
        assert(match is not None)
        timestamp = datetime.fromisoformat(match['timestamp'])

        assert('staff_id' in item)
        staff_id = item['staff_id']
        if staff_id != 'SYSTEM':
            assert(staff_id.isdecimal())
            staff_id = int(staff_id)

        assert('added' in item)
        assert(type(item['added']) is bool)
        action = 'added' if item['added'] else 'removed'

        assert('emoji' in item)
        emoji = bytes(item['emoji']).decode()

        assert('reason' in item)
        reason = item['reason']

        return RobomojiTransaction(timestamp, staff_id, user_id, action, emoji, reason)

    response = the_table().query(
        KeyConditionExpression='id = :id AND begins_with(sk, :sk_prefix)',
        ExpressionAttributeValues={
            ':id': _make_id(user_id),
            ':sk_prefix': _make_sk(_update_prefix),
        },
        ScanIndexForward=False,
        Limit=limit,
    )
    return [
        make_robomoji_transaction(item)
        for item in response.get('Items', [])
    ]

def get_emoji_info(user_id: int) -> tuple[datetime | None, list[str]]:
    response = the_table().get_item(
        Key=_make_key(user_id, 'info'),
        ProjectionExpression='emojis, last_reacted'
    )
    item = response.get('Item', {})
    last_reacted_raw: str | None = item.get('last_reacted')  # type: ignore
    emojis_raw: set[SupportsBytes] = item.get('emojis', set())  # type: ignore

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
