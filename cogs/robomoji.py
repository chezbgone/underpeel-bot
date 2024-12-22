import logging

from discord import HTTPException, Interaction, Member, Message, app_commands
from discord.ext import commands

from config import CONFIG
from database.robomoji_db import get_emojis, toggle_emoji

LOG = logging.getLogger(__name__)

@app_commands.guild_only
@app_commands.guilds(CONFIG['discord_server_id'])
class RobomojiCog(commands.GroupCog, group_name='robomoji'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        emojis = get_emojis(message.author.id)
        for emoji in emojis:
            try:
                await message.add_reaction(emoji)
            except HTTPException as e:
                if e.code == 10014:
                    LOG.error(f"emoji '{emoji}' does not exist. removing from database.")
                    toggle_emoji(message.author.id, emoji)

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
