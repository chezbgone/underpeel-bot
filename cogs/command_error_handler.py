import logging

import discord
from discord import Interaction, app_commands
from discord.ext import commands
from discord.ext.commands import CommandError, Context

from models.bot import Bot

LOG = logging.getLogger(__name__)

async def on_tree_error(interaction: Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingAnyRole):
        await interaction.response.send_message(
            "You don't have the permission for this command.",
            ephemeral=True,
        )
        return
    raise error

# from https://gist.github.com/EvieePy/7822af90858ef65012ea500bcecf1612
class CommandErrorHandler(commands.Cog):
    def __init__(self, bot: Bot):
        bot.tree.on_error = on_tree_error

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error: CommandError):
        """The event triggered when an error is raised while invoking a command.
        Parameters
        ------------
        ctx: commands.Context
            The context used for command invocation.
        error: commands.CommandError
            The Exception raised.
        """
        if hasattr(ctx.command, 'on_error'):
            return

        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        ignored = (commands.CommandNotFound, )
        error = getattr(error, 'original', error)
        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.DisabledCommand):
            await ctx.send(f'{ctx.command} has been disabled.')

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
            except discord.HTTPException:
                pass

        elif isinstance(error, commands.BadArgument):
            assert(ctx.command is not None)
            if ctx.command.qualified_name == 'tag list':
                await ctx.send('I could not find that member. Please try again.')

        else:
            raise error
