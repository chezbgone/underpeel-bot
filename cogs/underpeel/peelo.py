import asyncio

from discord import (
    AllowedMentions,
    Interaction,
    Member,
    Role,
    app_commands,
)

from config import CONFIG
from database.valorant import get_riot_id
from models.bot import Bot
from models.peelo import (
    NotEligible,
    PlayerStats,
)

staff_check = app_commands.checks.has_any_role(
    CONFIG['dev_role_id'],
    CONFIG['board_role_id'],
    CONFIG['mod_role_id'],
    CONFIG['logistics_role_id'],
)

def role_eligibility(player: Member) -> list[Role]:
    return [r for r in player.roles if r.id in CONFIG['up_participation_roles']]

async def eligibility(bot: Bot, player: Member) -> tuple[int | None, str]:
    """
    returns (peelo, checks)
    """
    riot_id = get_riot_id(player.id)
    if riot_id is None:
        header = f'{player.mention}'
        g_details = '-# :warning: No Riot ID linked to user.'
        peelo = None
    else:
        header = f'{player.mention} ({riot_id.tracker()})'
        eligible = (await PlayerStats.of(riot_id, bot.http_session)).eligibility()
        g_details = '-# ' + eligible.display()
        match eligible:
            case NotEligible():
                peelo = None
            case e:
                peelo = e.peak.peelo()

    match role_eligibility(player):
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
            g_details,
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
