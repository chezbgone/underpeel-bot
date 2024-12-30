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
import database.robomoji_db as db

LOG = logging.getLogger(__name__)

ROBOMOJI_COOLDOWN = timedelta(seconds=30)
management_check = app_commands.checks.has_any_role(
    CONFIG['board_role_id'],
    CONFIG['mod_role_id'],
    CONFIG['dev_role_id'],
)

@app_commands.guilds(CONFIG['discord_server_id'])
class RobomojiCog(commands.GroupCog, group_name='robomoji'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.guild is None:
            return
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
        last_reacted, emojis = db.get_emoji_info(author_id)
        if len(emojis) == 0:
            return
        if (
            last_reacted is not None and
            last_reacted + ROBOMOJI_COOLDOWN > datetime.now()
        ):
            # too soon, don't add reactions
            return
        db.register_emoji_use(author_id)
        for emoji in emojis:
            try:
                await message.add_reaction(emoji)
            except HTTPException as e:
                if e.code == 10014 or (e.code == 50035 and 'emoji_id' in e.text):
                    LOG.error(
                        f"emoji '{emoji}' for {message.author.id}({message.author.name}) "
                        f"does not exist. removing from database.",
                    )
                    db.toggle_emoji('SYSTEM', author_id, emoji, 'bot could not find emoji')
                

    @app_commands.command(name='toggle')
    @management_check
    @app_commands.describe(
        member='member to add the robomoji to',
        emoji='emoji to become the reaction',
        reason='reason for toggling'
    )
    async def toggle_emoji(
        self,
        interaction: Interaction,
        member: Member,
        emoji: str,
        reason: str,
    ):
        act = db.toggle_emoji(interaction.user.id, member.id, emoji, reason)
        act_preposition = lambda action: 'to' if action == 'added' else 'from'
        LOG.info(
            f'{interaction.user} {act} robomoji {emoji} '
            f'{act_preposition(act)} {member} (reason: {reason})'
        )
        await interaction.response.send_message(f'{act} robomoji {emoji} {act_preposition(act)} {member}')

    @app_commands.command(name='list')
    @management_check
    @app_commands.describe(
        member='member to describe emojis for',
    )
    async def list_emoji(self, interaction: Interaction, member: Member):
        _, emojis = db.get_emoji_info(member.id)
        if len(emojis) == 0:
            await interaction.response.send_message(f'{member.name} has no robomojis')
            return
        await interaction.response.send_message(' '.join(emojis))

    @app_commands.command(name='history')
    @management_check
    @app_commands.describe(
        member='member to get emoji history for',
        limit='how many transactions to display (default: 15)',
    )
    async def emoji_history(self, interaction: Interaction, member: Member, limit: int=15):
        history = db.get_emoji_changes(member.id, limit)
        act_preposition = lambda action: 'to' if action == "added" else 'from'
        mention_staff = lambda staff: 'SYSTEM' if staff == 'SYSTEM' else f'<@{staff}>'
        response = [
            f'here are the most recent robomoji commands for {member.name}:',
            *(
                ' '.join((
                    f'<t:{round(transaction.time.timestamp())}>:',
                    mention_staff(transaction.staff),
                    transaction.action,
                    transaction.emoji,
                    act_preposition(transaction.action),
                    f'<@{transaction.chatter_id}>',
                    f'(reason: {transaction.reason})'
                ))
                for transaction in history
            )
        ]
        await interaction.response.send_message(
            '\n'.join(response),
            allowed_mentions=AllowedMentions.none()
        )

    @toggle_emoji.error
    @list_emoji.error
    @emoji_history.error
    async def permissions_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingAnyRole):
            await interaction.response.send_message(
                "You don't have the permission for this command.",
                ephemeral=True,
            )
            return
        raise error
