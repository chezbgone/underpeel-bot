import logging

import discord
from discord.ext import commands

LOG = logging.getLogger(__name__)

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        LOG.info(f'Logged in as {self.user}')

