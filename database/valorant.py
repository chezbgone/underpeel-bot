import logging

from pydantic import BaseModel

from database import GetItemResponse, the_table
from models.valorant import RiotId

LOG = logging.getLogger(__name__)

#####  SCHEMA  #####


# user#{userid}, valorant#riotid
class DbRiotId(BaseModel):
    game_name: str
    tagline: str

    def finalize(self) -> RiotId:
        return RiotId(self.game_name, self.tagline)


#####  UTILS  #####


def _make_id(user_id: int) -> str:
    return f"user#{user_id}"


def _make_key(user_id: int):
    return {"id": _make_id(user_id), "sk": "valorant#riotid"}


#####  INTERACTIONS  #####


def get_riot_id(user_id: int) -> RiotId | None:
    raw_response = the_table().get_item(
        Key=_make_key(user_id),
        ProjectionExpression="game_name, tagline",
    )
    response = GetItemResponse[DbRiotId].model_validate(raw_response)
    if response.item is None:
        return None
    return response.item.finalize()


def set_riot_id(user_id: int, game_name: str, tag: str):
    the_table().put_item(
        Item={
            **_make_key(user_id),
            "game_name": game_name,
            "tagline": tag,
        }
    )


def clear_riot_id(user_id: int):
    the_table().delete_item(
        Key=_make_key(user_id),
    )
