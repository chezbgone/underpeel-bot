import string
import uuid
from dataclasses import dataclass
from typing import Literal, Self

from discord import (
    Color,
    Embed,
    Message,
    TextChannel,
)

import database.predictions as db


@dataclass
class Prediction:
    id: str
    message_id: int
    title: str
    status: Literal["open", "closed", "paid"]
    choice_a: str
    choice_b: str
    votes_a: int
    votes_b: int

    @classmethod
    def _make_short_uuid(cls) -> str:
        alphabet = string.digits + string.ascii_letters
        alphabet_size = len(alphabet)
        integer = uuid.uuid4().int
        if integer == 0:
            return alphabet[0]
        acc = []
        while integer != 0:
            acc.append(alphabet[integer % alphabet_size])
            integer //= alphabet_size
        return "".join(reversed(acc))

    @classmethod
    async def new(
        cls, channel: TextChannel, title: str, choice_a: str, choice_b: str
    ) -> tuple[Self, Message, Embed]:
        prediction_id = cls._make_short_uuid()
        message = await channel.send("creating prediction")
        prediction = cls(
            id=prediction_id,
            message_id=message.id,
            title=title,
            status="open",
            choice_a=choice_a,
            choice_b=choice_b,
            votes_a=0,
            votes_b=0,
        )
        db.create_prediction(
            prediction_id, message.id, prediction.title, choice_a, choice_b
        )
        embed = prediction.update_embed(Embed(color=Color.random()))
        return prediction, message, embed

    @classmethod
    def from_db(cls, info: db.PredictionInfo):
        return cls(
            id=info.prediction_id,
            message_id=info.message_id,
            title=info.title,
            status=info.status,
            choice_a=info.choice_a,
            choice_b=info.choice_b,
            votes_a=info.votes_a,
            votes_b=info.votes_b,
        )

    def update_embed(
        self, embed: Embed, winner: Literal["a", "b"] | None = None
    ) -> Embed:
        def pluralize(n: int, noun: str) -> str:
            return f"{n} {noun}" if n == 1 else f"{n} {noun}s"

        def make_label(votes: int, winner: bool = False) -> str:
            return f"{pluralize(votes, 'point')}" + (" (WINNER)" if winner else "")

        return (
            embed.clear_fields()
            .add_field(
                name=self.choice_a,
                value=make_label(self.votes_a, winner == "a"),
                inline=True,
            )
            .add_field(
                name=self.choice_b,
                value=make_label(self.votes_b, winner == "b"),
                inline=True,
            )
        )
