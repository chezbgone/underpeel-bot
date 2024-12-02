import asyncio
import logging

import discord
from discord.ext import commands

from config import SECRETS
from cogs.command_error_handler import CommandErrorHandler

intents = discord.Intents.all()

discord.utils.setup_logging(level=logging.INFO)
LOG = logging.getLogger(__name__)

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    LOG.info(f'Logged in as {bot.user}')
    await bot.add_cog(CommandErrorHandler(bot))
    LOG.info('done')

async def main():
    await bot.start(SECRETS['DISCORD_TOKEN'])

if __name__ == '__main__':
    asyncio.run(main())
