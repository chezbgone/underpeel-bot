from discord import app_commands

from config import CONFIG
from .link import link, staff_link, staff_unlink, unlink, valorant_info

@app_commands.guilds(CONFIG['discord_server_id'])
class Underpeel(app_commands.Group, name='underpeel'):
    def __init__(self):
        super().__init__()

        # self.add_command(link)
        # self.add_command(unlink)
        self.add_command(valorant_info)

    class Staff(app_commands.Group, name='staff'):
        def __init__(self):
            super().__init__()
            self.add_command(staff_link)
            self.add_command(staff_unlink)
