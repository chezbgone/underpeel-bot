from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class WithDataclassRepr:
    def __repr__(self) -> str:
        if not hasattr(self, "_repr_cache"):
            self.__repr__cache = dataclass(self.__class__).__repr__
        return self.__repr__cache(self)


class Base(WithDataclassRepr, DeclarativeBase):
    pass


#####    CURRENCY    #####


class CurrencyInfo(Base):
    __tablename__ = "currency"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int]


#####    ROBOMOJI    #####


class RobomojiInfo(Base):
    __tablename__ = "robomoji_info"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    last_reacted: Mapped[datetime]
    robomojis: Mapped[list["Robomoji"]] = relationship(lazy="joined")


class Robomoji(Base):
    __tablename__ = "robomojis"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("robomoji_info.user_id"))
    emoji: Mapped[str]


class RobomojiTransactionKind(Enum):
    ADDED = "added"
    REMOVED = "removed"


class RobomojiTransaction(Base):
    __tablename__ = "robomoji_transactions"
    __table_args__ = (
        CheckConstraint(
            "system != (staff_id IS NOT NULL)",  # interpret != as XOR
            "system_or_staff",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chatter_id: Mapped[int]
    emoji: Mapped[str]
    time: Mapped[datetime]
    system: Mapped[bool]
    staff_id: Mapped[int] = mapped_column(nullable=True)
    reason: Mapped[str]
    action: Mapped[RobomojiTransactionKind]


#####    RIOTID    #####


class RiotId(Base):
    __tablename__ = "riot_ids"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    game_name: Mapped[str]
    tagline: Mapped[str]


#####    PREDICTIONS    #####


class PredictionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    PAID = "paid"


class PredictionChoice(Enum):
    A = "a"
    B = "b"


class Prediction(Base):
    __tablename__ = "predictions"

    message_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    status: Mapped[PredictionStatus]
    choice_a: Mapped[str]
    choice_b: Mapped[str]
    votes: Mapped[list["PredictionVote"]] = relationship()


class PredictionVote(Base):
    __tablename__ = "prediction_votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction: Mapped[int] = mapped_column(ForeignKey("predictions.message_id"))
    user_id: Mapped[int]
    amount: Mapped[int]
    choice: Mapped[PredictionChoice]
