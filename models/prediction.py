from dataclasses import dataclass
from typing import Self

from discord import (
    Color,
    Embed,
    Message,
)

import database.predictions as db


def _pluralize(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


@dataclass
class PredictionInfo:
    message: Message
    title: str
    choice_a: str
    choice_b: str
    status: db.PredictionStatus

    votes_a: int = 0
    votes_b: int = 0
    winner: db.PredictionChoice | None = None

    @classmethod
    def from_db(cls, prediction: db.Prediction, prediction_message: Message) -> Self:
        return cls(
            message=prediction_message,
            title=prediction.title,
            choice_a=prediction.choice_a,
            choice_b=prediction.choice_b,
            status=prediction.status,
            winner=prediction.winner,
        )

    def make_embed(self, base_embed: Embed | None = None) -> Embed:
        def make_label(votes: int, winner: bool = False) -> str:
            return f"{_pluralize(votes, 'point')}" + (" (WINNER)" if winner else "")

        if base_embed is None:
            embed = Embed(color=Color.random(), title=self.title)
        else:
            embed = base_embed.clear_fields()

        if self.status == db.PredictionStatus.REFUNDED:
            embed.title = f"[REFUNDED] {embed.title}"

        embed.add_field(
            name=self.choice_a,
            value=make_label(self.votes_a, self.winner == db.PredictionChoice.A),
            inline=True,
        ).add_field(
            name=self.choice_b,
            value=make_label(self.votes_b, self.winner == db.PredictionChoice.B),
            inline=True,
        )

        return embed
