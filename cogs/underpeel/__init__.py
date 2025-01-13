from discord import app_commands

from config import CONFIG
from .link import link, valorant_info

@app_commands.guilds(CONFIG['discord_server_id'])
class Underpeel(app_commands.Group, name='underpeel'):
    def __init__(self):
        super().__init__()
        self.add_command(link)
        self.add_command(valorant_info)
