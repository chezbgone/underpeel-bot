import asyncio
import logging

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
    NotEligible,
    PlayerStats,
)
from models.valorant import ActInfo, ImmortalPlus, RiotId, SimpleRank

LOG = logging.getLogger(__name__)

staff_check = app_commands.checks.has_any_role(
    CONFIG['dev_role_id'],
    CONFIG['board_role_id'],
    CONFIG['mod_role_id'],
    CONFIG['logistics_role_id'],
)

async def player_stats_from_tracker(riot_id: RiotId, http_session: ClientSession) -> PlayerStats | None:
    def parse_act_info(act_json) -> ActInfo:
        act_name = act_json['metadata']['name']
        played = act_json['stats']['matchesPlayed']['value']
        peak_name = act_json['stats']['peakRank']['metadata']['tierName']

        peak = SimpleRank.try_from(peak_name)
        if peak is None and peak_name in ['Immortal 1', 'Immortal 2', 'Immortal 3', 'Radiant']:
            peak_value = act_json['stats']['peakRank']['value']
            peak = ImmortalPlus(peak_name, peak_value)
        return ActInfo(act_name, played, peak)

    url = (
        f'https://api.track'
        'er.gg/api/v2/valorant/'
        'standard/profile/riot/'
        f'{riot_id.game_name}%23{riot_id.tag}/'
        'segments/season-report'
    )
    params = { 'playlist': 'competitive' }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.1',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }
    async with http_session.get(url, params=params, headers=headers) as response:
        if response.status == 403:
            return None
        try:
            res = await response.json()
            seasons = [
                'E9: A1',
                'E9: A2',
                'E9: A3',
                'V25: A1',
            ]
            season_dict = {
                d['metadata']['name']: parse_act_info(d)
                for d in res['data']
                if d['type'] == 'season-report'
                if d['metadata']['name'] in seasons
            }
            return PlayerStats(*(
                season_dict.get(season, ActInfo.empty(season))
                for season in seasons
            ))

        except Exception as e:
            LOG.warning('could not get stats from tracker', exc_info=e)
            return None

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
        peak_name = peak_data['name']
        peak = SimpleRank.try_from(peak_name)
        if peak is None and peak_name in ['Immortal 1', 'Immortal 2', 'Immortal 3', 'Radiant']:
            peak = ImmortalPlus(peak_name, None)
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
            LOG.warning('could not get stats from henrikdev api', exc_info=e)
            return None

async def eligibility(bot: Bot, player: Member) -> tuple[int | None, str]:
    """
    returns (peelo, checks)
    """
    riot_id = get_riot_id(player.id)
    if riot_id is None:
        header = f'{player.mention}'
        game_details = '-# :warning: No Riot ID linked to user.'
        peelo = None
    else:
        header = f'{player.mention} ({riot_id.tracker()})'
        if (pstats := await player_stats_from_tracker(riot_id, bot.http_session)) is not None:
            eligible = pstats.eligibility()
        elif (pstats := await player_stats_from_henrik(riot_id, bot.http_session)) is not None:
            eligible = pstats.eligibility()
        else:
            eligible = NotEligible()
        game_details = '-# ' + eligible.details()
        match eligible:
            case NotEligible():
                peelo = None
            case _:
                if eligible.peak is None:
                    peelo = None
                else:
                    peelo = eligible.peak.peelo()

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
        peelo,
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
        peelos, details = zip(*eligibilities)
        all_details = '\n'.join(details)
        if None not in peelos:
            all_details += f'\n**Total peelo: {sum(peelos)}**'
        await interaction.followup.send(
            all_details,
            allowed_mentions=AllowedMentions.none(),
        )
    return check_team_eligibility
