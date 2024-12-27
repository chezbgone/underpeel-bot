from datetime import datetime, timedelta
import logging

from discord import (
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
from database.robomoji_db import get_emoji_info, register_emoji_use, toggle_emoji

LOG = logging.getLogger(__name__)

ROBOMOJI_COOLDOWN = timedelta(seconds=30)

@app_commands.guild_only
@app_commands.guilds(CONFIG['discord_server_id'])
class RobomojiCog(commands.GroupCog, group_name='robomoji'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        assert(message.guild is not None)
        if message.guild.id != CONFIG['discord_server_id']:
            return

        channel = message.channel
        if isinstance(channel, Thread):
            channel = channel.parent
            assert(channel is not None)

        match channel:
            case TextChannel() | StageChannel() | VoiceChannel() | ForumChannel():
                if channel.id in CONFIG['non_robomoji_channels']:
                    return
                if channel.category_id in CONFIG['non_robomoji_categories']:
                    return
            case _:
                LOG.info('tried to robomoji in bad {channel=}')

        author_id = message.author.id
        last_reacted, emojis = get_emoji_info(author_id)
        if len(emojis) == 0:
            return
        if (
            last_reacted is not None and
            last_reacted + ROBOMOJI_COOLDOWN > datetime.now()
        ):
            # too soon, don't add reactions
            return
        register_emoji_use(author_id)
        for emoji in emojis:
            try:
                await message.add_reaction(emoji)
            except HTTPException as e:
                if e.code == 10014:
                    LOG.error(f"emoji '{emoji}' does not exist. removing from database.")
                    toggle_emoji(author_id, emoji)

    @app_commands.command()
    @app_commands.checks.has_any_role(
        CONFIG['board_role_id'],
        CONFIG['mod_role_id'],
        CONFIG['dev_role_id'],
    )
    @app_commands.describe(
        member='member to add the robomoji to',
        emoji='emoji to become the reaction',
    )
    async def toggle_emoji(self, interaction: Interaction, member: Member, emoji: str):
        res = toggle_emoji(member.id, emoji)
        LOG.info(f'{interaction.user} {res} robomoji {emoji} for {member}')
        await interaction.response.send_message(f'{res} robomoji {emoji} for {member}')

    @toggle_emoji.error
    async def toggle_emoji_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingAnyRole):
            await interaction.response.send_message(
                "You don't have the permission for this command.",
                ephemeral=True,
            )
            return
        raise error
