import asyncio
import logging

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from config import CONFIG, SECRETS
from cogs.command_error_handler import CommandErrorHandler
from cogs.robomoji import RobomojiCog

intents = discord.Intents.all()

discord.utils.setup_logging(level=logging.INFO)
LOG = logging.getLogger(__name__)

bot = commands.Bot(command_prefix='!', intents=intents)
guild = discord.Object(id=CONFIG['discord_server_id'])

@bot.event
async def on_ready():
    LOG.info(f'Logged in as {bot.user}')
    await bot.add_cog(CommandErrorHandler(bot))
    await bot.add_cog(RobomojiCog(bot))
    LOG.info('done')

@bot.tree.command(guild=guild)
@app_commands.checks.has_any_role(
    CONFIG['board_role_id'],
    CONFIG['mod_role_id'],
    CONFIG['dev_role_id'],
)
async def sync(interaction: Interaction):
    synced = await bot.tree.sync(guild=guild)
    await interaction.response.send_message(f'synced {len(synced)} commands')

async def main():
    await bot.start(SECRETS['DISCORD_TOKEN'])

if __name__ == '__main__':
    asyncio.run(main())
