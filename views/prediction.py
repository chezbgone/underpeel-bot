from discord import AllowedMentions, Interaction, ui

import database.predictions as db
from models.prediction import PredictionInfo, _pluralize


class PredictionView(ui.View):
    def __init__(self, info: PredictionInfo):
        super().__init__(timeout=None)

        if info.votes_a == 0 or info.votes_b == 0:
            label_a = info.choice_a
            label_b = info.choice_b
        else:
            total_votes = info.votes_a + info.votes_b
            a_payout = total_votes / info.votes_a
            b_payout = total_votes / info.votes_b
            label_a = f"{info.choice_a} (×{a_payout:.2f})"
            label_b = f"{info.choice_b} (×{b_payout:.2f})"

        # callbacks in PredictionsCog.on_interaction for presistence over bot restarts
        self.add_item(
            ui.Button(
                label=label_a,
                custom_id=f"up_prediction:{info.message.id}:a",
                disabled=info.status != db.PredictionStatus.OPEN,
            )
        )
        self.add_item(
            ui.Button(
                label=label_b,
                custom_id=f"up_prediction:{info.message.id}:b",
                disabled=info.status != db.PredictionStatus.OPEN,
            )
        )


class PredictionAmountPrompt(ui.Modal):
    def __init__(
        self,
        info: PredictionInfo,
        choice: db.PredictionChoice,
        user_balance: int,
    ):
        choice_label = (
            info.choice_a if choice == db.PredictionChoice.A else info.choice_b
        )
        super().__init__(title=f"Predicting {choice_label}")

        self.info = info
        self.choice = choice

        self.amount = ui.TextInput(label=f"amount (max {user_balance})")
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
            message_id=self.info.message.id,
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
                    "not enough peels", ephemeral=True
                )
                return
            case "nonexistent prediction":
                await interaction.response.send_message(
                    "could not find prediction", ephemeral=True
                )
                return
            case updated_prediction_info:
                self.info.votes_a = updated_prediction_info[db.PredictionChoice.A]
                self.info.votes_b = updated_prediction_info[db.PredictionChoice.B]

        choice_name = (
            self.info.choice_a
            if self.choice == db.PredictionChoice.A
            else self.info.choice_b
        )
        await interaction.response.send_message(
            f"Received {self.amount} for {choice_name}", ephemeral=True
        )

        message = await self.info.message.fetch()
        assert message is not None and len(message.embeds) == 1
        [embed] = message.embeds
        new_embed = self.info.make_embed(embed)
        new_view = PredictionView(self.info)
        await message.edit(embed=new_embed, view=new_view)

        assert message.thread is not None
        await message.thread.send(
            f"{interaction.user.mention} put {_pluralize(amount, 'peel')} on {choice_name}",
            allowed_mentions=AllowedMentions.none(),
        )


class PredictionCloseControls(ui.View):
    def __init__(self, info: PredictionInfo) -> None:
        super().__init__(timeout=None)
        self.info = info

    @ui.button(label="Close Prediction", emoji="🚫")
    async def close_prediction(self, interaction: Interaction, _: ui.Button):
        result = db.close_prediction(self.info.message.id)
        match result:
            case "prediction has already been closed":
                await interaction.response.edit_message(
                    view=PredictionPayoutControls(self.info)
                )
            case "prediction has already been paid":
                await interaction.response.send_message(result)
                return

        # disable voting buttons
        message = await self.info.message.fetch()
        view = ui.View.from_message(message)
        for choice_button in view.children:
            assert isinstance(choice_button, ui.Button)
            choice_button.disabled = True
        self.prediction_message = await message.edit(view=view)

        assert message.thread is not None
        await message.thread.send("Prediction closed!")

        # change controls
        await interaction.response.edit_message(
            view=PredictionPayoutControls(self.info)
        )


class PayoutButton(ui.Button):
    def __init__(
        self,
        info: PredictionInfo,
        winner: db.PredictionChoice,
    ):
        self.info = info
        self.winner = winner

        self.choice_label = (
            info.choice_a if winner == db.PredictionChoice.A else info.choice_b
        )
        super().__init__(label=f"Payout {self.choice_label}")

    async def callback(self, interaction: Interaction):
        result = db.pay_out_prediction(self.info.message.id, self.winner)
        match result:
            case "prediction has already been paid out":
                await interaction.response.send_message(result, ephemeral=True)
                return
        prediction = db.get_prediction(self.info.message.id)
        assert prediction is not None
        info = PredictionInfo.from_db(prediction, self.info.message)

        # disable payout buttons
        assert interaction.message is not None
        view = ui.View.from_message(interaction.message)
        for button in view.children:
            assert isinstance(button, ui.Button)
            button.disabled = True
        await interaction.response.edit_message(view=view)

        # edit embed to show winner
        message = await info.message.fetch()
        assert len(message.embeds) == 1
        [embed] = message.embeds
        embed = info.make_embed(base_embed=embed)
        await message.edit(embed=embed)

        # send message in thread
        assert message.thread is not None
        await message.thread.send(
            f"Prediction has been paid out to {self.choice_label}"
        )


class PredictionPayoutControls(ui.View):
    def __init__(self, info: PredictionInfo) -> None:
        super().__init__(timeout=None)

        self.add_item(PayoutButton(info, db.PredictionChoice.A))
        self.add_item(PayoutButton(info, db.PredictionChoice.B))
