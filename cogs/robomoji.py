from datetime import datetime, timedelta
import logging

from discord import (
    AllowedMentions,
    ForumChannel,
    HTTPException,
    Interaction,
    Member,
    Message,
    TextChannel,
    Thread,
    StageChannel,
    VoiceChannel,
    app_commands,
)
from discord.ext import commands

from config import CONFIG
import database.robomoji as db

LOG = logging.getLogger(__name__)

ROBOMOJI_COOLDOWN = timedelta(seconds=30)
management_check = app_commands.checks.has_any_role(
    CONFIG["board_role_id"],
    CONFIG["mod_role_id"],
    CONFIG["dev_role_id"],
)


def _display_robomoji_transaction(transaction: db.RobomojiTransaction) -> str:
    return " ".join(
        (
            f"<t:{round(transaction.time.timestamp())}>:",
            "SYSTEM"
            if transaction.staff_id == "SYSTEM"
            else f"<@{transaction.staff_id}>",
            transaction.action.value,
            transaction.emoji,
            "to" if transaction.action.value == "added" else "from",
            f"<@{transaction.chatter_id}>",
            f"(reason: {transaction.reason})",
        )
    )


@app_commands.guilds(CONFIG["discord_server_id"])
class RobomojiCog(commands.GroupCog, group_name="robomoji"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.guild is None:
            return
        if message.guild.id != CONFIG["discord_server_id"]:
            return

        channel = message.channel
        if isinstance(channel, Thread):
            channel = channel.parent
            assert channel is not None

        match channel:
            case TextChannel() | StageChannel() | VoiceChannel() | ForumChannel():
                if channel.id in CONFIG["non_robomoji_channels"]:
                    return
                if channel.category_id in CONFIG["non_robomoji_categories"]:
                    return
            case _:
                LOG.info("tried to robomoji in bad {channel=}")

        author_id = message.author.id
        emoji_info = db.get_emoji_info(author_id)
        if emoji_info is None:
            return
        if len(emoji_info.robomojis) == 0:
            return
        if (
            emoji_info.last_reacted is not None
            and emoji_info.last_reacted + ROBOMOJI_COOLDOWN > datetime.now()
        ):
            # too soon, don't add reactions
            return
        db.register_emoji_use(author_id)
        for robomoji in emoji_info.robomojis:
            try:
                await message.add_reaction(robomoji.emoji)
            except HTTPException as e:
                if e.code == 10014 or (e.code == 50035 and "emoji_id" in e.text):
                    LOG.error(
                        f"emoji '{robomoji.emoji}' for {message.author.id}({message.author.name}) "
                        f"does not exist. removing from database.",
                    )
                    db.toggle_emoji(
                        "SYSTEM", author_id, robomoji.emoji, "bot could not find emoji"
                    )

    @app_commands.command(name="toggle")
    @management_check
    @app_commands.describe(
        member="member to add the robomoji to",
        emoji="emoji to become the reaction",
        reason="reason for toggling",
    )
    async def toggle_emoji(
        self,
        interaction: Interaction,
        member: Member,
        emoji: str,
        reason: str,
    ):
        action = db.toggle_emoji(interaction.user.id, member.id, emoji, reason)
        act_preposition = "to" if action.value == "added" else "from"
        LOG.info(
            f"{interaction.user} {action} robomoji {emoji} "
            f"{act_preposition} {member} (reason: {reason})"
        )
        await interaction.response.send_message(
            f"{action.value} robomoji {emoji} {act_preposition} {member}",
            allowed_mentions=AllowedMentions.none(),
        )

    @app_commands.command(name="list")
    @management_check
    @app_commands.describe(
        member="member to describe emojis for",
    )
    async def list_emoji(self, interaction: Interaction, member: Member):
        emoji_info = db.get_emoji_info(member.id)
        if emoji_info is None or len(emoji_info.robomojis) == 0:
            await interaction.response.send_message(f"{member.name} has no robomojis")
            return
        await interaction.response.send_message(
            " ".join(robomoji.emoji for robomoji in emoji_info.robomojis)
        )

    @app_commands.command(name="history")
    @management_check
    @app_commands.describe(
        member="member to get emoji history for",
        limit="how many transactions to display (default: 15)",
    )
    async def emoji_history(
        self, interaction: Interaction, member: Member, limit: int = 15
    ):
        history = db.get_emoji_changes(member.id, limit)
        response = [
            f"here are the most recent robomoji commands for {member.name}:",
            *(_display_robomoji_transaction(transaction) for transaction in history),
        ]
        await interaction.response.send_message(
            "\n".join(response), allowed_mentions=AllowedMentions.none()
        )
