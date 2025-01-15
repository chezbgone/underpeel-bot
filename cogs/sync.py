import logging

import discord
from discord import (
    Interaction,
    app_commands,
)

from config import CONFIG
from models.bot import Bot

LOG = logging.getLogger(__name__)

def mk_sync(bot: Bot):
    @app_commands.command()
    @app_commands.guilds(CONFIG['discord_server_id'])
    @app_commands.checks.has_any_role(
        CONFIG['board_role_id'],
        CONFIG['mod_role_id'],
        CONFIG['dev_role_id'],
    )
    async def sync(interaction: Interaction):
        guild = discord.Object(id=CONFIG['discord_server_id'])
        synced = await bot.tree.sync(guild=guild)
        LOG.info(f'{synced=}')
        await interaction.response.send_message(
            f'Synced {len(synced)} commands',
            ephemeral=True,
        )
    return sync
