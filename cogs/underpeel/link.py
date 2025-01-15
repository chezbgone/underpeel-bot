import logging

from discord import (
    AllowedMentions,
    Interaction,
    Member,
    app_commands,
)
from discord.app_commands import Range

from database.valorant import clear_riot_id, get_riot_id, set_riot_id
from config import CONFIG

LOG = logging.getLogger(__name__)

staff_check = app_commands.checks.has_any_role(
    CONFIG['dev_role_id'],
    CONFIG['board_role_id'],
    CONFIG['mod_role_id'],
    CONFIG['logistics_role_id'],
)

def _check_riot_id(riot_id: str) -> tuple[str, str] | str:
    match riot_id.split('#'):
        case [game_name, tag]:
            pass
        case _:
            return 'Invalid format. Expected `gamename#tag`.'
    
    if not (3 <= len(tag) <= 5):
        return 'Invalid Riot ID. Tagline should be between 3 and 5 characters long.'
    if not tag.isalnum():
        return "Invalid Riot ID. Tagline should only consist of alphanumeric characters."

    return (game_name, tag)

@app_commands.command()
async def link(interaction: Interaction, riot_id: Range[str, 7]):
    respond = interaction.response.send_message
    match _check_riot_id(riot_id):
        case (game_name, tag):
            pass
        case error_message:
            await respond(error_message)
            return

    set_riot_id(interaction.user.id, game_name, tag)
    await respond(f'Successfully linked to `{game_name}#{tag}`')

@app_commands.command()
async def unlink(interaction: Interaction):
    clear_riot_id(interaction.user.id)
    await interaction.response.send_message(f'Successfully unlinked Riot ID.')

@app_commands.command(name='link')
@staff_check
async def staff_link(interaction: Interaction, player: Member, riot_id: Range[str, 7]):
    respond = interaction.response.send_message
    match _check_riot_id(riot_id):
        case (game_name, tag):
            pass
        case error_message:
            await respond(error_message)
            return
    set_riot_id(player.id, game_name, tag)
    await respond(
        f'Successfully linked {player.mention} to `{game_name}#{tag}`',
        allowed_mentions=AllowedMentions.none(),
    )

@app_commands.command(name='unlink')
@staff_check
async def staff_unlink(interaction: Interaction, player: Member):
    clear_riot_id(player.id)
    await interaction.response.send_message(
        f'Successfully unlinked Riot ID from {player.mention}.',
        allowed_mentions=AllowedMentions.none(),
    )

@app_commands.command()
async def valorant_info(interaction: Interaction, player: Member):
    riot_id = get_riot_id(player.id)
    if riot_id is None:
        await interaction.response.send_message(
            f'No Riot id found for user',
        )
        return
    await interaction.response.send_message(riot_id, ephemeral=True)
