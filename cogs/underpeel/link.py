import logging

from discord import (
    Interaction,
    Member,
    app_commands,
)
from discord.app_commands import Range

from database.valorant import get_riot_id, set_riot_id

LOG = logging.getLogger(__name__)

@app_commands.command()
async def link(interaction: Interaction, riot_id: Range[str, 7]):
    match riot_id.split('#'):
        case [game_name, tag]:
            pass
        case _:
            await interaction.response.send_message('Invalid format. Expected `gamename#tag`.')
            return
    
    respond = interaction.response.send_message
    if not (3 <= len(tag) <= 5):
        await respond('Invalid Riot ID. Tagline should be between 3 and 5 characters long.')
        return
    if not tag.isalnum():
        await respond("Invalid Riot ID. Tagline should only consist of alphanumeric characters.")
        return

    set_riot_id(interaction.user.id, game_name, tag)
    await respond(f'Successfully linked to `{game_name}#{tag}`')

@app_commands.command()
async def valorant_info(interaction: Interaction, player: Member):
    riot_id = get_riot_id(player.id)
    if riot_id is None:
        await interaction.response.send_message(
            f'No Riot id found for user',
        )
        return
    await interaction.response.send_message(riot_id, ephemeral=True)
