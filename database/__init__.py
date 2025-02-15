import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import (
    Base,
    # re-export
    CurrencyInfo as CurrencyInfo,
    RobomojiInfo as RobomojiInfo,
    Robomoji as Robomoji,
    RobomojiTransaction as RobomojiTransaction,
    RiotId as RiotId,
    Prediction as Prediction,
    PredictionStatus as PredictionStatus,
    PredictionChoice as PredictionChoice,
    PredictionVote as PredictionVote,
)

LOG = logging.getLogger(__name__)

engine = create_engine("sqlite:///underpeel.db")
_SessionFactory = sessionmaker(bind=engine)


def make_session():
    Base.metadata.create_all(engine)
    return _SessionFactory()
