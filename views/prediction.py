from typing import Literal
from discord import AllowedMentions, Interaction, Message, ui

import database.predictions as db
from models.prediction import Prediction


class PredictionView(ui.View):
    def __init__(self, prediction: Prediction):
        super().__init__(timeout=None)

        if prediction.votes_a == 0 or prediction.votes_b == 0:
            label_a = prediction.choice_a
            label_b = prediction.choice_b
        else:
            total_votes = prediction.votes_a + prediction.votes_b
            a_payout = total_votes / prediction.votes_a
            b_payout = total_votes / prediction.votes_b
            label_a = f"{prediction.choice_a} (×{a_payout:.2f})"
            label_b = f"{prediction.choice_b} (×{b_payout:.2f})"

        # callbacks in PredictionsCog.on_interaction for presistence over bot restarts
        self.add_item(
            ui.Button(label=label_a, custom_id=f"up_prediction:{prediction.id}:a")
        )
        self.add_item(
            ui.Button(label=label_b, custom_id=f"up_prediction:{prediction.id}:b")
        )


class PredictionAmountPrompt(ui.Modal):
    def __init__(
        self,
        prediction: Prediction,
        prediction_message: Message,
        choice: Literal["a", "b"],
        balance: int,
    ):
        choice_label = prediction.choice_a if choice == "a" else prediction.choice_b
        super().__init__(title=f"Predicting {choice_label}")
        self.prediction = prediction
        self.prediction_message = prediction_message
        self.choice: Literal["a", "b"] = choice

        self.amount = ui.TextInput(label=f"amount (max {balance})")
        self.add_item(self.amount)

    async def on_submit(self, interaction: Interaction):
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "amount must be a positive integer", ephemeral=True
            )
            return
        response = db.add_prediction_vote(
            prediction_id=self.prediction.id,
            user_id=interaction.user.id,
            choice=self.choice,
            amount=amount,
        )
        match response:
            case "prediction is not open":
                await interaction.response.send_message(
                    "prediction is no longer open", ephemeral=True
                )
                return
            case "not enough points":
                await interaction.response.send_message(
                    "not enough points", ephemeral=True
                )
                return
            case "nonexistent prediction":
                await interaction.response.send_message(
                    "could not find prediction", ephemeral=True
                )
                return
            case "unknown error":
                await interaction.response.send_message(
                    "could not add vote", ephemeral=True
                )
                return
            case updated_prediction_info:
                self.prediction = Prediction.from_db(updated_prediction_info)

        choice_name = (
            self.prediction.choice_a if self.choice == "a" else self.prediction.choice_b
        )
        await interaction.response.send_message(
            f"Received {self.amount} for {choice_name}", ephemeral=True
        )

        message = self.prediction_message
        assert message is not None and len(message.embeds) == 1
        [embed] = message.embeds
        new_embed = self.prediction.update_embed(embed)
        new_view = PredictionView(self.prediction)
        await message.edit(embed=new_embed, view=new_view)

        assert message.thread is not None

        def pluralize(n, noun: str):
            return f"{n} {noun}" if n == 1 else f"{n} {noun}s"

        await message.thread.send(
            f"{interaction.user.mention} put {pluralize(amount, 'point')} on {choice_name}",
            allowed_mentions=AllowedMentions.none(),
        )


class PredictionCloseControls(ui.View):
    def __init__(self, prediction: Prediction, prediction_message: Message) -> None:
        super().__init__(timeout=None)
        self.prediction = prediction
        self.prediction_message = prediction_message

    @ui.button(label="Close Prediction", emoji="🚫")
    async def close_prediction(self, interaction: Interaction, _: ui.Button):
        assert interaction.message is not None
        result = db.close_prediction(self.prediction.id)
        match result:
            case "prediction has already been closed":
                await interaction.response.edit_message(
                    view=PredictionPayoutControls(
                        self.prediction, self.prediction_message
                    )
                )
            case "prediction has already been paid":
                await interaction.response.send_message(result)
                return
            case "could not close prediction":
                await interaction.response.send_message(result)
                return

        # disable buttons
        message = await self.prediction_message.fetch()
        view = ui.View.from_message(message)
        for choice_button in view.children:
            assert isinstance(choice_button, ui.Button)
            choice_button.disabled = True
        self.prediction_message = await message.edit(view=view)

        assert message.thread is not None
        await message.thread.send("Prediction closed!")

        # change controls
        await interaction.response.edit_message(
            view=PredictionPayoutControls(self.prediction, self.prediction_message)
        )


class PayoutButton(ui.Button):
    def __init__(
        self,
        prediction: Prediction,
        prediction_message: Message,
        choice: Literal["a", "b"],
    ):
        self.prediction = prediction
        self.prediction_message = prediction_message
        self.winner: Literal["a", "b"] = choice

        self.choice_label = (
            prediction.choice_a if choice == "a" else prediction.choice_b
        )
        super().__init__(label=f"Payout {self.choice_label}")

    async def callback(self, interaction: Interaction):
        result = db.pay_out_prediction(self.prediction.id, self.winner)
        match result:
            case "prediction has already been paid out":
                await interaction.response.send_message(result, ephemeral=True)
                return
            case "could not pay out prediction":
                await interaction.response.send_message(result, ephemeral=True)
                return
            case updated_prediction_info:
                self.prediction = Prediction.from_db(updated_prediction_info)

        # disable button
        assert interaction.message is not None
        view = ui.View.from_message(interaction.message)
        for button in view.children:
            assert isinstance(button, ui.Button)
            button.disabled = True
        await interaction.response.edit_message(view=view)

        # edit prediction_message to show winner
        message = await self.prediction_message.fetch()
        assert len(message.embeds) == 1
        [embed] = message.embeds
        embed = self.prediction.update_embed(embed, winner=self.winner)
        await self.prediction_message.edit(embed=embed)

        # send message in thread
        assert message.thread is not None
        await message.thread.send(
            f"Prediction has been paid out to {self.choice_label}"
        )


class PredictionPayoutControls(ui.View):
    def __init__(self, prediction: Prediction, prediction_message: Message) -> None:
        super().__init__(timeout=None)

        self.add_item(PayoutButton(prediction, prediction_message, "a"))
        self.add_item(PayoutButton(prediction, prediction_message, "b"))
