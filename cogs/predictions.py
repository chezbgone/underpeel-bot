import re
from discord import (
    Interaction,
    TextChannel,
    Thread,
    app_commands,
)
from discord.ext import commands

import database.predictions as db
from config import CONFIG
from models.bot import Bot
from models.prediction import PredictionInfo
from views.prediction import (
    PredictionAmountPrompt,
    PredictionCloseControls,
    PredictionPayoutControls,
    PredictionView,
)

management_check = app_commands.checks.has_any_role(
    CONFIG["board_role_id"],
    CONFIG["mod_role_id"],
    CONFIG["dev_role_id"],
)


@app_commands.guilds(CONFIG["discord_server_id"])
class PredictionsCog(commands.GroupCog, group_name="prediction"):
    def __init__(self, bot: Bot) -> None:
        super().__init__()
        self.bot = bot

    @app_commands.command(name="create")
    @management_check
    async def start_prediction(
        self,
        interaction: Interaction,
        title: str,
        choice_a: str,
        choice_b: str,
    ):
        channel = interaction.channel
        if channel is None or not isinstance(channel, TextChannel):
            await interaction.response.send_message(
                "Can't create a prediction here", ephemeral=True
            )
            return
        message = await channel.send("creating prediction")
        db.create_prediction(message.id, title, choice_a, choice_b)

        info = PredictionInfo(
            message=message,
            title=title,
            choice_a=choice_a,
            choice_b=choice_b,
            status=db.PredictionStatus.OPEN,
        )

        view = PredictionView(info)
        embed = info.make_embed()

        await message.edit(content=None, embed=embed, view=view)
        await channel.create_thread(name=f"Prediction: {title}", message=message)
        await interaction.response.send_message(
            view=PredictionCloseControls(info),
            ephemeral=True,
        )

    @app_commands.command(name="show_controls")
    @management_check
    async def show_controls(
        self,
        interaction: Interaction,
    ):
        thread = interaction.channel
        if thread is None or not isinstance(thread, Thread):
            await interaction.response.send_message(
                "Please use this command inside of the prediction's thread",
                ephemeral=True,
            )
            return
        assert thread.starter_message is not None
        prediction = db.get_prediction(thread.starter_message.id)
        if prediction is None:
            await interaction.response.send_message(
                "This thread is not a prediction thread",
                ephemeral=True,
            )
            return
        info = PredictionInfo.from_db(prediction, thread.starter_message)
        match prediction.status:
            case db.PredictionStatus.OPEN:
                await interaction.response.send_message(
                    view=PredictionCloseControls(info),
                    ephemeral=True,
                )
            case db.PredictionStatus.CLOSED:
                await interaction.response.send_message(
                    view=PredictionPayoutControls(info),
                    ephemeral=True,
                )
            case db.PredictionStatus.PAID:
                await interaction.response.send_message(
                    "prediction has already been paid out",
                    ephemeral=True,
                )

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        if interaction.data is None:
            return
        button_id = interaction.data.get("custom_id")
        if not isinstance(button_id, str):
            return
        pattern = re.compile(
            r"up_prediction:(?P<message_id>\d+):(?P<prediction_choice_id>[ab])"
        )
        if (match := pattern.fullmatch(button_id)) is None:
            # interaction is not of interest
            return
        message_id = int(match["message_id"])
        choice = (
            db.PredictionChoice.A
            if match["prediction_choice_id"] == "a"
            else db.PredictionChoice.B
        )

        prediction = db.get_prediction(message_id)
        assert prediction is not None
        if prediction is None:
            await interaction.response.send_message(
                "could not find prediction", ephemeral=True
            )
            return

        assert interaction.message is not None
        info = PredictionInfo.from_db(prediction, interaction.message)
        await interaction.response.send_modal(
            PredictionAmountPrompt(
                info,
                choice,
                user_balance=db.get_user_points(interaction.user.id),
            )
        )
        return
