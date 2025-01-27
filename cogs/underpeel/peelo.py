import asyncio
import logging
from typing import cast

from aiohttp import ClientSession
from discord import (
    AllowedMentions,
    Interaction,
    Member,
    app_commands,
)

from config import CONFIG, SECRETS
from database.valorant import get_riot_id
from models.bot import Bot
from models.peelo import (
    ActInfo,
    NotEligible,
    PlayerStats,
    Rank,
    peelo_of,
    rank_from_name,
)
from models.valorant import ImmortalPlus, RiotId, SimpleRank

LOG = logging.getLogger(__name__)

staff_check = app_commands.checks.has_any_role(
    CONFIG['dev_role_id'],
    CONFIG['board_role_id'],
    CONFIG['mod_role_id'],
    CONFIG['logistics_role_id'],
)

async def player_stats_from_henrik(riot_id: RiotId, http_session: ClientSession) -> PlayerStats | None:
    def parse_act_info(act_json) -> ActInfo | None:
        act_name = act_json['season']['short']
        played = act_json['games']
        peak_data = max(
            act_json['act_wins'],
            default=None,
            key=lambda win: win['id'],
        )
        if peak_data is None:
            return None
        peak = rank_from_name(peak_data['name'])
        return ActInfo(act_name, played, peak)

    url = f'https://api.henrikdev.xyz/valorant/v3/mmr/na/pc/{riot_id.game_name}/{riot_id.tag}'
    headers = { 'Authorization': SECRETS['HENRIKDEV_KEY'] }
    async with http_session.get(url, headers=headers) as response:
        try:
            res = await response.json()
            seasons = [
                'e9a1',
                'e9a2',
                'e9a3',
                'e10a1',
            ]
            season_dict: dict[str, ActInfo] = {
                season['season']['short']: act_info
                for season in res['data']['seasonal']
                if season['season']['short'] in seasons
                if (act_info := parse_act_info(season)) is not None
            }
            return PlayerStats(*(
                season_dict.get(season, ActInfo.empty(season))
                for season in seasons
            ))
        except Exception as e:
            LOG.warning(f'could not get stats for {riot_id}', exc_info=e)
            return None

async def eligibility(bot: Bot, player: Member) -> tuple[Rank | None, str]:
    """
    returns (peak_rank, checks)
    """
    riot_id = get_riot_id(player.id)
    if riot_id is None:
        header = f'{player.mention}'
        game_details = '-# :warning: No Riot ID linked to user.'
        peak_rank = None
    else:
        header = f'{player.mention} ({riot_id.tracker()})'
        player_stats = await player_stats_from_henrik(riot_id, bot.http_session)
        if player_stats is None:
            game_details = f'-# :warning: Info for {riot_id} not found.'
            peak_rank = None
        else:
            eligible = player_stats.eligibility()
            game_details = '-# ' + eligible.details()
            match eligible:
                case NotEligible():
                    peak_rank = None
                case _:
                    peak_rank = eligible.peak

    qualifying_roles = [r for r in player.roles if r.id in CONFIG['up_participation_roles']]
    match qualifying_roles:
        case []:
            r_details = '-# :x: Player does not have any qualifying role.'
        case roles:
            r_details = (
                f'-# :white_check_mark: Player has roles: '
                f"{' '.join(role.mention for role in roles)}"
            )

    return (
        peak_rank,
        '\n'.join((
            header,
            game_details,
            r_details,
        )),
    )

def mk_check_eligibility(bot: Bot):
    @app_commands.command()
    @staff_check
    async def check_eligibility(interaction: Interaction, player: Member):
        await interaction.response.defer(ephemeral=True)
        _, details = await eligibility(bot, player)
        await interaction.followup.send(
            details,
            allowed_mentions=AllowedMentions.none()
        )
    return check_eligibility

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
        eligibilities = await asyncio.gather(*(
            eligibility(bot, p)
            for p in players
        ))
        peaks: tuple[Rank | None, ...]
        details: tuple[str, ...]
        peaks, details = zip(*eligibilities)

        summary = []
        if all(isinstance(p, SimpleRank) for p in peaks):
            peelo = sum(peelo_of(p) for p in cast(list[SimpleRank], peaks))
            summary.append(f'**Total peelo: {peelo}**')
        if sum(isinstance(p, ImmortalPlus) for p in peaks) <= 2:
            summary.append(f':white_check_mark: **Team has at most two Immortal+ players.**')
        else:
            summary.append(f':x: **Team has more than two Immortal+ players.**')

        await interaction.followup.send(
            '\n'.join((*details, *summary)),
            allowed_mentions=AllowedMentions.none(),
        )
    return check_team_eligibility
