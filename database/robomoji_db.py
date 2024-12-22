import logging
from typing import Literal

from database import the_table

_key = lambda user_id: { 'id': user_id, 'sk': 'robomoji' }

LOG = logging.getLogger(__name__)

def get_emojis(user_id: int) -> set[str]:
    response = the_table().get_item(
        Key=_key(user_id),
        ProjectionExpression='emojis'
    )
    if 'Item' not in response:
        return set()
    if 'emojis' not in response['Item']:
        return set()
    emojis = response['Item']['emojis']
    return {bytes(emoji).decode() for emoji in emojis}  # type: ignore

def toggle_emoji(user_id: int, emoji: str) -> Literal['added', 'removed']:
    user_emojis = get_emojis(user_id)
    if emoji in user_emojis:
        update_expression = 'DELETE emojis :emoji'
        ret = 'removed'
    else:
        update_expression = 'ADD emojis :emoji'
        ret = 'added'

    res = the_table().update_item(
        Key=_key(user_id),
        UpdateExpression=update_expression,
        ExpressionAttributeValues={
            # unicode string emojis get messed up in transit
            ':emoji': {emoji.encode()},
        },
        ReturnValues='ALL_NEW',
    )
    LOG.info(res['Attributes'])
    return ret
