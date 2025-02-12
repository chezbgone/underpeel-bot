import asyncio
import logging

import discord

from cogs.command_error_handler import CommandErrorHandler
from cogs.currency import CurrencyCog
from cogs.predictions import PredictionsCog
from cogs.robomoji import RobomojiCog
from cogs.sync import mk_sync
from cogs.underpeel import Underpeel
from config import CONFIG, SECRETS
from models.bot import Bot


async def main():
    bot = Bot()
    no_color_formatter = logging.Formatter(
        "{levelname:<8} | {name}: {message}", style="{"
    )
    if CONFIG["production_mode"]:
        discord.utils.setup_logging(formatter=no_color_formatter)
    else:
        discord.utils.setup_logging()

    await bot.add_cog(CommandErrorHandler(bot))
    await bot.add_cog(RobomojiCog(bot))
    await bot.add_cog(CurrencyCog(bot))
    await bot.add_cog(PredictionsCog(bot))
    bot.tree.add_command(mk_sync(bot))
    bot.tree.add_command(Underpeel(bot))

    await bot.start(SECRETS["DISCORD_TOKEN"])


if __name__ == "__main__":
    asyncio.run(main())
