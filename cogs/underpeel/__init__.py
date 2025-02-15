from discord import app_commands

from models.bot import Bot
from config import CONFIG
from .link import staff_link, staff_unlink, valorant_info
from .peelo import mk_check_eligibility, mk_check_team_eligibility


@app_commands.guilds(CONFIG["discord_server_id"])
class Underpeel(app_commands.Group, name="underpeel"):
    def __init__(self, bot: Bot):
        super().__init__()
        self.add_command(Underpeel.Staff(bot))

        # self.add_command(link)
        # self.add_command(unlink)
        self.add_command(valorant_info)

    class Staff(app_commands.Group, name="staff"):
        def __init__(self, bot: Bot):
            super().__init__()
            self.add_command(staff_link)
            self.add_command(staff_unlink)
            self.add_command(mk_check_eligibility(bot))
            self.add_command(mk_check_team_eligibility(bot))
