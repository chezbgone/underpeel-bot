import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from discord import AllowedMentions, Interaction, Member, Message, app_commands
from discord.ext import commands, tasks

import database.currency as db
from config import CONFIG
from models.bot import Bot

LOG = logging.getLogger(__name__)

management_check = app_commands.checks.has_any_role(
    CONFIG["board_role_id"],
    CONFIG["mod_role_id"],
    CONFIG["dev_role_id"],
)

ACCRUAL_COOLDOWN = timedelta(minutes=10)
ACCUMULATION_DELAY = timedelta(minutes=10)
ACCRUAL_CURRENCY_AMOUNT = 1
STREAM_CHAT_MULTIPLIER = 10


@dataclass
class CurrencyCooldown:
    """
    based off of discord.py's Cooldown class
    """

    window: datetime
    in_stream: bool = False

    def _try_use(self) -> bool:
        """
        returns whether cooldown was used and updated
        """
        now = datetime.now()
        if self.window + ACCRUAL_COOLDOWN < now:
            if now < self.window + ACCRUAL_COOLDOWN + ACCUMULATION_DELAY:
                self.window += ACCRUAL_COOLDOWN
            else:
                self.window = now
            return True
        return False

    def try_use_normal(self) -> bool:
        """
        returns whether cooldown was used and updated
        """
        if self._try_use():
            self.in_stream = False
            return True
        return False

    def try_use_stream(self) -> Literal["blocked", "promoted", "accepted"]:
        if self._try_use():
            self.in_stream = True
            return "accepted"
        elif not self.in_stream:
            self.in_stream = True
            return "promoted"
        return "blocked"


class CurrencyCooldownMap:
    def __init__(self) -> None:
        self.map: dict[int, CurrencyCooldown] = {}

    def _clean_cache(self):
        def cutoff(t: datetime) -> datetime:
            return t + ACCRUAL_COOLDOWN + ACCUMULATION_DELAY

        dead_keys = [
            k for (k, v) in self.map.items() if datetime.now() > cutoff(v.window)
        ]
        for k in dead_keys:
            del self.map[k]

    def try_use_normal(self, member: Member) -> bool:
        if member.id not in self.map:
            self.map[member.id] = CurrencyCooldown(datetime.now())
            return True
        return self.map[member.id].try_use_normal()

    def try_use_stream(
        self, member: Member
    ) -> Literal["blocked", "promoted", "accepted"]:
        if member.id not in self.map:
            self.map[member.id] = CurrencyCooldown(datetime.now(), in_stream=True)
            return "accepted"
        return self.map[member.id].try_use_stream()


@app_commands.guilds(CONFIG["discord_server_id"])
class CurrencyCog(commands.GroupCog, group_name="currency"):
    def __init__(self, bot: Bot):
        super().__init__()
        self.bot = bot
        self.cooldowns = CurrencyCooldownMap()
        self.clear_cooldown_cache.start()

        assert self.app_command is not None
        self.app_command.add_command(CurrencyStaff())

    async def cog_unload(self):
        self.clear_cooldown_cache.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot:
            return
        if message.guild is None or message.guild.id != CONFIG["discord_server_id"]:
            return
        if not isinstance(message.author, Member):
            return
        if message.channel.id == CONFIG["stream_chat_id"]:
            match self.cooldowns.try_use_stream(message.author):
                case "accepted":
                    amount = ACCRUAL_CURRENCY_AMOUNT * STREAM_CHAT_MULTIPLIER
                case "promoted":
                    amount = ACCRUAL_CURRENCY_AMOUNT * (STREAM_CHAT_MULTIPLIER - 1)
                case "blocked":
                    return
            db.add_points_to_user(message.author.id, amount)
            return
        if self.cooldowns.try_use_normal(message.author):
            db.add_points_to_user(message.author.id, ACCRUAL_CURRENCY_AMOUNT)

    @app_commands.command(name="balance")
    async def check_balance(self, interaction: Interaction):
        points = db.get_user_points(interaction.user.id)
        point_plural = "point" if points == 1 else "points"
        await interaction.response.send_message(
            f"You have {points} {point_plural}.",
            ephemeral=True,
        )

    @tasks.loop(hours=1)
    async def clear_cooldown_cache(self):
        self.cooldowns._clean_cache()


@app_commands.guilds(CONFIG["discord_server_id"])
class CurrencyStaff(app_commands.Group, name="staff"):
    @app_commands.command(name="balance")
    @management_check
    async def check_balance(self, interaction: Interaction, member: Member):
        points = db.get_user_points(member.id)
        point_plural = "point" if points == 1 else "points"
        await interaction.response.send_message(
            f"{member.mention} has {points} {point_plural}.",
            allowed_mentions=AllowedMentions.none(),
            ephemeral=True,
        )

    @app_commands.command(name="give")
    @management_check
    async def give_currency(
        self, interaction: Interaction, member: Member, amount: int
    ):
        new_amount = db.add_points_to_user(member.id, amount)
        LOG.info(
            f"{interaction.user} ({interaction.user.id}) gave {member} ({member.id}) {amount} currency"
        )
        await interaction.response.send_message(
            f"Added {amount} to {member.mention}'s balance. They now have {new_amount}.",
            allowed_mentions=AllowedMentions.none(),
            ephemeral=True,
        )
