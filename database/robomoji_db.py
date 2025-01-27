import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from database import GetItemResponse, QueryResponse, the_table

LOG = logging.getLogger(__name__)

#####  SCHEMA  #####

# user#{userid}, robomoji#update#{timestamp}
class RobomojiTransaction(BaseModel):
    time: datetime = Field(validation_alias='sk')
    staff: int | Literal['SYSTEM'] = Field(validation_alias='staff_id')
    chatter_id: int = Field(validation_alias='id')
    action: Literal['added', 'removed'] = Field(validation_alias='added')
    emoji: str
    reason: str

    @field_validator('chatter_id', mode='before')
    @classmethod
    def trim_id(cls, id: str):
        return id.removeprefix('user#')

    @field_validator('time', mode='before')
    @classmethod
    def trim_sk(cls, sk: str):
        return sk.removeprefix('robomoji#update#')

    @field_validator('action', mode='before')
    @classmethod
    def validate_added(cls, added: bool) -> Literal['added', 'removed']:
        return 'added' if added else 'removed'

# user#{userid}, robomoji#info
class RobomojiInfo(BaseModel):
    emojis: list[str]
    last_reacted: datetime | None = Field(default=None)

#####  UTILS  #####

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

#####  INTERACTIONS  #####

def get_emoji_changes(user_id: int, limit=15) -> list[RobomojiTransaction]:
    raw_response = the_table().query(
        KeyConditionExpression='id = :id AND begins_with(sk, :sk_prefix)',
        ExpressionAttributeValues={
            ':id': _make_id(user_id),
            ':sk_prefix': _make_sk(_update_prefix),
        },
        ScanIndexForward=False,
        Limit=limit,
    )
    response = QueryResponse[RobomojiTransaction].model_validate(raw_response)
    return response.items

def get_emoji_info(user_id: int) -> RobomojiInfo | None:
    raw_response = the_table().get_item(
        Key=_make_key(user_id, 'info'),
        ProjectionExpression='emojis, last_reacted'
    )
    response = GetItemResponse[RobomojiInfo].model_validate(raw_response)
    return response.item

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
    if (emoji_info := get_emoji_info(user_id)) is None:
        user_emojis = []
    else:
        user_emojis = emoji_info.emojis

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
