import logging
from typing import cast
from uuid import UUID

from aiohttp import ClientSession
from discord import (
    AllowedMentions,
    Interaction,
    Member,
    Role,
    app_commands,
)
from pydantic import BaseModel, Field

from config import CONFIG, SECRETS
from database.valorant import get_riot_id
from models.bot import Bot
from models.peelo import (
    ActInfo,
    Episode10Eligibility,
    Episode9Eligibility,
    NotEligible,
    PlayerStats,
    Rank,
    StatsEligibility,
    peelo_of,
    rank_from_name,
)
from models.valorant import ImmortalPlus, RiotId, SimpleRank

LOG = logging.getLogger(__name__)

staff_check = app_commands.checks.has_any_role(
    CONFIG["dev_role_id"],
    CONFIG["board_role_id"],
    CONFIG["mod_role_id"],
    CONFIG["logistics_role_id"],
)


class ResponseActWin(BaseModel):
    id: int
    name: str


class ResponseActMeta(BaseModel):
    id: UUID
    short: str


class ResponseAct(BaseModel):
    metadata: ResponseActMeta = Field(validation_alias="season")
    wins: int
    games: int
    act_wins: list[ResponseActWin]


class MmrResponseData(BaseModel):
    seasonal: list[ResponseAct]


async def ranked_matches_from_henrik(
    riot_id: RiotId, http_session: ClientSession
) -> PlayerStats | None:
    def parse_act_info(act: ResponseAct) -> ActInfo | None:
        act_name = act.metadata.short
        played = act.games
        peak_data = max(
            act.act_wins,
            default=None,
            key=lambda win: win.id,
        )
        if peak_data is None:
            return None
        peak = rank_from_name(peak_data.name)
        return ActInfo(act_name, played, peak)

    url = f"https://api.henrikdev.xyz/valorant/v3/mmr/na/pc/{riot_id.game_name}/{riot_id.tag}"
    headers = {"Authorization": SECRETS["HENRIKDEV_KEY"]}
    async with http_session.get(url, headers=headers) as response:
        try:
            raw_response = await response.json()
            if raw_response["status"] != 200:
                raise ValueError(raw_response)
            response_data = MmrResponseData.model_validate(raw_response["data"])
            acts = ["e9a1", "e9a2", "e9a3", "e10a1"]
            act_dict: dict[str, ActInfo] = {
                act.metadata.short: act_info
                for act in response_data.seasonal
                if (act_info := parse_act_info(act)) is not None
            }
            return PlayerStats(
                *(act_dict.get(act_name, ActInfo.empty(act_name)) for act_name in acts)
            )
        except Exception:
            LOG.info(f"could not get valorant stats for {riot_id}")
            return None


type MatchesInfo = (
    tuple[RiotId, None, None]
    | tuple[RiotId, StatsEligibility, None]
    | tuple[RiotId, StatsEligibility, Rank]
)


async def get_matches_info(http_session: ClientSession, riot_id: RiotId) -> MatchesInfo:
    ranked_matches = await ranked_matches_from_henrik(riot_id, http_session)
    if ranked_matches is None:
        return (riot_id, None, None)
    match ranked_matches.eligibility():
        case NotEligible():
            return (riot_id, NotEligible(), None)
        case Episode9Eligibility() | Episode10Eligibility() as e:
            return (riot_id, ranked_matches.eligibility(), e.peak)


async def maybe_get_matches_info(
    http_session: ClientSession, riot_id: RiotId | None
) -> MatchesInfo | None:
    if riot_id is None:
        return None
    return await get_matches_info(http_session, riot_id)


type RoleInfo = list[Role]


def get_role_info(player: Member) -> list[Role]:
    return [r for r in player.roles if r.id in CONFIG["up_participation_roles"]]


def display_eligibility_info(
    player: Member, matches_info: MatchesInfo | None, role_info: RoleInfo
) -> str:
    match matches_info:
        case None as riot_id:
            game_details = "-# :warning: No Riot ID linked to user."
        case (riot_id, None, _):
            game_details = f"-# :warning: Info for {riot_id} not found."
        case (riot_id, eligibility, _):
            game_details = "-# " + eligibility.details()

    header = player.mention
    if riot_id is not None:
        header = f"{player.mention} ({riot_id.tracker()})"

    if not role_info:
        role_details = "-# :x: Player does not have any qualifying role."
    else:
        role_mentions = " ".join(role.mention for role in role_info)
        role_details = f"-# :white_check_mark: Player has roles: {role_mentions}"

    return "\n".join(
        (
            header,
            game_details,
            role_details,
        )
    )


def mk_check_eligibility(bot: Bot):
    @app_commands.command()
    @staff_check
    async def check_eligibility(interaction: Interaction, player: Member):
        await interaction.response.defer(ephemeral=True)
        riot_id = get_riot_id(player.id)
        matches_info = await maybe_get_matches_info(bot.http_session, riot_id)
        role_info = get_role_info(player)
        await interaction.followup.send(
            display_eligibility_info(player, matches_info, role_info),
            allowed_mentions=AllowedMentions.none(),
        )

    return check_eligibility


def display_team_eligibility_info(
    players: list[Member],
    matches_infos: list[MatchesInfo | None],
    role_infos: list[RoleInfo],
) -> str:
    argss = list(zip(players, matches_infos, role_infos, strict=True))
    individual_eligibility_infos = [display_eligibility_info(*args) for args in argss]

    def peak_of_info(info: MatchesInfo | None) -> Rank | None:
        if info is None:
            return None
        _, _, peak = info
        return peak

    peaks = [peak_of_info(info) for info in matches_infos]
    team_summary = []
    if all(isinstance(peak, SimpleRank) for peak in peaks):
        peaks = cast(list[SimpleRank], peaks)
        total_peelo = sum(peelo_of(peak) for peak in peaks)
        team_summary.append(f"**Total peelo: {total_peelo}**")
    if sum(isinstance(peak, ImmortalPlus) for peak in peaks) <= 2:
        team_summary.append(
            ":white_check_mark: **Team has at most two Immortal+ players.**"
        )
    else:
        team_summary.append(":x: **Team has more than two Immortal+ players.**")

    return "\n".join((*individual_eligibility_infos, *team_summary))


def mk_check_team_eligibility(bot: Bot):
    @app_commands.command()
    @staff_check
    async def check_team_eligibility(
        interaction: Interaction,
        player1: Member,
        player2: Member,
        player3: Member,
        player4: Member,
        player5: Member,
    ):
        await interaction.response.defer(ephemeral=True)
        players = [player1, player2, player3, player4, player5]
        maybe_riot_ids = [get_riot_id(p.id) for p in players]
        matches_infos = [
            await maybe_get_matches_info(bot.http_session, riot_id)
            for riot_id in maybe_riot_ids
        ]
        role_infos = [get_role_info(p) for p in players]

        await interaction.followup.send(
            display_team_eligibility_info(players, matches_infos, role_infos),
            allowed_mentions=AllowedMentions.none(),
        )

    return check_team_eligibility
