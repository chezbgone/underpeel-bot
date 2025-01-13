import asyncio
import logging

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from cogs.command_error_handler import CommandErrorHandler
from cogs.robomoji import RobomojiCog
from cogs.underpeel import Underpeel
from config import CONFIG, SECRETS

no_color_formatter = logging.Formatter('{levelname:<8} | {name}: {message}', style='{')
if CONFIG['production_mode']:
    discord.utils.setup_logging(formatter=no_color_formatter)
else:
    discord.utils.setup_logging()
LOG = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
guild = discord.Object(id=CONFIG['discord_server_id'])

@bot.event
async def on_ready():
    LOG.info(f'Logged in as {bot.user}')

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
    await bot.add_cog(CommandErrorHandler(bot))
    await bot.add_cog(RobomojiCog(bot))
    bot.tree.add_command(Underpeel())

    await bot.start(SECRETS['DISCORD_TOKEN'])

if __name__ == '__main__':
    asyncio.run(main())
