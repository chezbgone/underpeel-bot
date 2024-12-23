import logging
from datetime import datetime
from typing import Literal

from database import the_table

_key = lambda user_id: { 'id': user_id, 'sk': 'robomoji' }

LOG = logging.getLogger(__name__)

def get_emoji_info(user_id: int) -> tuple[datetime | None, set[str]]:
    response = the_table().get_item(
        Key=_key(user_id),
        ProjectionExpression='emojis, last_reacted'
    )
    last_reacted_raw: str | None = response.get('Item', {}).get('last_reacted')  # type: ignore
    emojis_raw: set[SupportsBytes] = response.get('Item', {}).get('emojis', set())  # type: ignore

    last_reacted = None
    if last_reacted_raw is not None:
        last_reacted = datetime.fromisoformat(last_reacted_raw)

    emojis = {bytes(emoji).decode() for emoji in emojis_raw}

    return last_reacted, emojis

def register_emoji_use(user_id: int):
    the_table().update_item(
        Key=_key(user_id),
        UpdateExpression='SET last_reacted = :t',
        ExpressionAttributeValues={
            ':t': datetime.now().isoformat(),
        },
    )

def toggle_emoji(user_id: int, emoji: str) -> Literal['added', 'removed']:
    _, user_emojis = get_emoji_info(user_id)
    if emoji in user_emojis:
        update_expression = 'DELETE emojis :emoji'
        ret = 'removed'
    else:
        update_expression = 'ADD emojis :emoji'
        ret = 'added'

    the_table().update_item(
        Key=_key(user_id),
        UpdateExpression=update_expression,
        ExpressionAttributeValues={
            # unicode string emojis get messed up in transit
            ':emoji': {emoji.encode()},
        },
    )
    return ret
