import asyncio
import logging
import sys
from os.path import dirname, abspath, join

import discord
from discord.ext import commands

# skull (make importing config easier)
PROJECT_ROOT = abspath(join(dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

from config import CONFIG, SECRETS

intents = discord.Intents.all()

discord.utils.setup_logging(level=logging.INFO)
LOG = logging.getLogger(__name__)

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    LOG.info(f'Logged in as {bot.user}')

    guild = bot.get_guild(CONFIG['discord_server_id'])
    assert(guild is not None)

    participant_role = guild.get_role(CONFIG['participant_role_id'])
    assert(participant_role is not None)
    for member in participant_role.members:
        await member.remove_roles(participant_role, reason='[chezbgone] Automatic end-of-season removal')
        LOG.info(f'removed participant role from {member.name}')

    captain_role = guild.get_role(CONFIG['captain_role_id'])
    assert(captain_role is not None)
    LOG.info('===================')
    for member in captain_role.members:
        await member.remove_roles(captain_role, reason='[chezbgone] Automatic end-of-season removal')
        LOG.info(f'removed captain role from {member.name}')
        LOG.info(member.name)

    LOG.info('done')

async def main():
    await bot.start(SECRETS['DISCORD_TOKEN'])

if __name__ == '__main__':
    asyncio.run(main())
