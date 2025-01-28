import logging
from typing import Literal, NotRequired, TypedDict

from database import the_table
from models.underpeel import Player, UnderpeelTeam

LOG = logging.getLogger(__name__)

"""
SCHEMA:
=======
user#{userid}, team : {
    tricode: str
}

teams, team#{tricode}: {
    name: str
    tricode: str
    coach: optional[{ userid: int }]
    players: list[{ userid: int, registered_peelo: int }]
}
"""


class PlayerDict(TypedDict):
    userid: int
    registered_peelo: int


class CoachDict(TypedDict):
    userid: int


class TeamDict(TypedDict):
    name: str
    tricode: str
    coach: NotRequired[CoachDict]
    players: list[PlayerDict]


def _serialize_player(p: Player) -> PlayerDict:
    return {
        "userid": p.discord_id,
        "registered_peelo": p.peelo,
    }


def _serialize_team(t: UnderpeelTeam) -> TeamDict:
    d: TeamDict = {
        "name": t.name,
        "tricode": t.name,
        "players": [_serialize_player(p) for p in t.players],
    }
    if t.coach is not None:
        d["coach"] = {"userid": t.coach}
    return d


def _deserialize_player(p: PlayerDict) -> Player:
    assert "userid" in p
    assert "registered_peelo" in p
    return Player(p["userid"], p["registered_peelo"])


def _deserialize_team(item) -> UnderpeelTeam:
    return UnderpeelTeam(
        name=item["name"],
        tricode=item["tricode"],
        coach=item.get("coach", {}).get("userid"),
        players={_deserialize_player(p) for p in item["players"]},
    )


def insert_team(team: UnderpeelTeam):
    with the_table().batch_writer() as b:
        b.put_item(
            Item={"id": "teams", "sk": f"team#{team.tricode}", **_serialize_team(team)}
        )
        for player in team.players:
            b.put_item(
                Item={
                    "id": f"user#{player.discord_id}",
                    "sk": "team",
                    "tricode": team.tricode,
                }
            )


def list_teams() -> list[UnderpeelTeam]:
    response = the_table().query(
        KeyConditionExpression="id = :id AND begins_with(sk, :sk_prefix)",
        ExpressionAttributeValues={
            ":id": "teams",
            ":sk_prefix": "team#",
        },
    )
    items = response.get("Items", [])
    teams: list[UnderpeelTeam] = []
    for item in items:
        try:
            team = _deserialize_team(item)
            teams.append(team)
        except Exception as e:
            LOG.error(f"could not deserialize team {item}", exc_info=e)

    return teams


def remove_team(tricode: str):
    response = the_table().delete_item(
        Key={
            "id": "teams",
            "sk": f"team#{tricode}",
        },
        ReturnValues="ALL_OLD",
    )
    if "Attributes" not in response:
        return "TeamNotFound"
    with the_table().batch_writer() as b:
        for p in response["Attributes"]["players"]:  # type: ignore
            player = _deserialize_player(p)
            b.delete_item(
                Key={
                    "id": f"user#{player.discord_id}",
                    "sk": "team",
                },
            )


def replace_player(
    tricode: str,
    old_player_id: int,
    new_player: Player,
):
    response = the_table().get_item(
        Key={
            "id": "teams",
            "sk": f"team#{tricode}",
        },
    )
    if "Item" not in response:
        return "TeamNotFound"
    team = _deserialize_team(response["Item"])
    players = list(team.players)
    for i, p in enumerate(players):  # type: ignore
        if p.discord_id == old_player_id:
            break
    else:
        return "PlayerNotOnTeam"
    players[i] = new_player
    the_table().update_item(
        Key={
            "id": "teams",
            "sk": f"team#{tricode}",
        },
        UpdateExpression="set players = :new_players",
        ExpressionAttributeValues={
            ":new_players": [_serialize_player(p) for p in players]
        },
    )


def get_team(tricode: str) -> UnderpeelTeam | Literal["TeamNotFound"]:
    response = the_table().get_item(
        Key={
            "id": "teams",
            "sk": f"team#{tricode}",
        },
    )
    if "Item" not in response:
        return "TeamNotFound"
    return _deserialize_team(response["Item"])
