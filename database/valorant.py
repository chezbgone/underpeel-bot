import logging

from database import the_table
from models.valorant import RiotId

LOG = logging.getLogger(__name__)

"""
SCHEMA:
=======
user#{userid}, valorant#riotid : {
    game_name: str
    tagline: str
}
"""

def _make_id(user_id: int) -> str:
    return f'user#{user_id}'

def _make_key(user_id: int):
    return {
        'id': _make_id(user_id),
        'sk': 'valorant#riotid'
    }

def get_riot_id(user_id: int) -> RiotId | None:
    response = the_table().get_item(
        Key=_make_key(user_id),
        ProjectionExpression='game_name, tagline',
    )
    item = response.get('Item')
    if item is None:
        LOG.info('riot id not found')
        return None

    assert('game_name' in item)
    assert('tagline' in item)
    game_name: str = item.get('game_name')  # type: ignore
    tag: str = item.get('tagline')  # type: ignore

    return RiotId(game_name, tag)

def set_riot_id(user_id: int, game_name: str, tag: str):
    the_table().put_item(
        Item={
            **_make_key(user_id),
            'game_name': game_name,
            'tagline': tag,
        }
    )

def clear_riot_id(user_id: int):
    the_table().delete_item(
        Key= _make_key(user_id),
    )
