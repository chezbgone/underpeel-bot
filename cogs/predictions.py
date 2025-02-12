import logging
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
from models.prediction import Prediction
from views.prediction import (
    PredictionAmountPrompt,
    PredictionCloseControls,
    PredictionPayoutControls,
    PredictionView,
)

LOG = logging.getLogger(__name__)

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
        prediction, p_message, embed = await Prediction.new(
            channel, title, choice_a, choice_b
        )
        view = PredictionView(prediction)
        p_message = await p_message.edit(content=None, embed=embed, view=view)
        await channel.create_thread(name=f"{title} votes", message=p_message)
        await interaction.response.send_message(
            view=PredictionCloseControls(prediction, p_message),
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
        prediction_id = db.get_prediction_id_from_message_id(thread.starter_message.id)
        assert (prediction_info := db.get_prediction(prediction_id)) is not None
        prediction = Prediction.from_db(prediction_info)
        match prediction.status:
            case "open":
                await interaction.response.send_message(
                    view=PredictionCloseControls(prediction, thread.starter_message),
                    ephemeral=True,
                )
            case "closed":
                await interaction.response.send_message(
                    view=PredictionPayoutControls(prediction, thread.starter_message),
                    ephemeral=True,
                )
            case "paid":
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
            r"up_prediction:(?P<prediction_id>\w+):(?P<prediction_choice_id>[ab])"
        )
        if (match := pattern.fullmatch(button_id)) is None:
            # interaction is not of interest
            return

        assert interaction.message is not None
        prediction_info = db.get_prediction(match["prediction_id"])
        if prediction_info is None:
            await interaction.response.send_message(
                "could not find prediction", ephemeral=True
            )
            return
        prediction = Prediction.from_db(prediction_info)

        await interaction.response.send_modal(
            PredictionAmountPrompt(
                prediction,
                interaction.message,
                match["prediction_choice_id"],  # type: ignore
                balance=db.get_user_points(interaction.user.id),
            )
        )
        return
