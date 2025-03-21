import logging
from collections import defaultdict
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database import (
    make_session,
    Prediction,
    PredictionVote,
    PredictionStatus,
    PredictionChoice,
)
from database.currency import add_points_to_user, get_user_points

LOG = logging.getLogger(__name__)


def create_prediction(message_id: int, title: str, choice_a: str, choice_b: str):
    with make_session() as session, session.begin():
        session.add(
            Prediction(
                message_id=message_id,
                title=title,
                status=PredictionStatus.OPEN,
                choice_a=choice_a,
                choice_b=choice_b,
                winner=None,
            )
        )


def get_prediction(message_id: int) -> Prediction | None:
    with make_session() as session:
        return session.scalar(
            select(Prediction)
            .where(Prediction.message_id == message_id)
            .options(joinedload(Prediction.votes))
        )


def get_votes_summary(message_id: int, session: Session):
    votes = session.execute(
        select(PredictionVote.choice, func.sum(PredictionVote.amount))
        .where(PredictionVote.prediction == message_id)
        .group_by(PredictionVote.choice)
    ).all()

    d: dict[PredictionChoice, int] = defaultdict(int)
    for choice, total_amount in votes:
        d[choice] = total_amount
    return d


def add_prediction_vote(
    message_id: int, user_id: int, choice: PredictionChoice, amount: int
):
    with make_session() as session, session.begin():
        prediction = session.get(Prediction, message_id)
        if prediction is None:
            LOG.error(
                f"{user_id=} voted for nonexistent prediction with message_id {message_id}"
            )
            return "nonexistent prediction"
        if prediction.status != PredictionStatus.OPEN:
            return "prediction is not open"

        if get_user_points(user_id) < amount:
            return "not enough points"

        choice_label = (
            prediction.choice_a if choice == PredictionChoice.A else prediction.choice_b
        )
        reason = f"voted for {choice} ({choice_label}) in prediction {message_id}"
        add_points_to_user(user_id, -amount, reason)

        vote = PredictionVote(
            prediction=message_id,
            user_id=user_id,
            amount=amount,
            choice=choice,
        )
        prediction.votes.append(vote)
        return get_votes_summary(message_id, session)


def close_prediction(message_id: int):
    with make_session() as session, session.begin():
        prediction = session.get(Prediction, message_id)
        if prediction is None:
            raise ValueError(f"could not find prediction attached to {message_id=}")
        if prediction.status == PredictionStatus.CLOSED:
            return "prediction has already been closed"
        if prediction.status == PredictionStatus.PAID:
            return "prediction has already been paid"
        prediction.status = PredictionStatus.CLOSED
        return get_votes_summary(message_id, session)


def pay_out_prediction(message_id: int, winner: PredictionChoice):
    with make_session() as session, session.begin():
        prediction = session.get(Prediction, message_id)
        if prediction is None:
            raise ValueError(f"could not find prediction attached to {message_id=}")
        if prediction.status == PredictionStatus.PAID:
            return "prediction has already been paid out"
        if prediction.status != PredictionStatus.CLOSED:
            raise ValueError(f"prediction attached to {message_id=} is not closed")

        votes = session.scalars(
            select(PredictionVote).where(PredictionVote.prediction == message_id)
        ).all()

        a_vote_amount = sum(
            vote.amount for vote in votes if vote.choice == PredictionChoice.A
        )
        b_vote_amount = sum(
            vote.amount for vote in votes if vote.choice == PredictionChoice.B
        )
        total_amount = a_vote_amount + b_vote_amount
        correct_vote_amount = (
            a_vote_amount if winner == PredictionChoice.A else b_vote_amount
        )

        if correct_vote_amount == 0:
            d = refund_prediction(message_id)
            assert d != "prediction has already been paid out"
            return "prediction has no winners", d

        for vote in votes:
            if vote.choice != winner:
                continue
            reward = ceil(total_amount * vote.amount / correct_vote_amount)
            print("adding", vote.user_id, reward)
            add_points_to_user(
                vote.user_id, reward, reason=f"prediction {message_id} payout"
            )

        prediction.status = PredictionStatus.PAID
        prediction.winner = winner
        return get_votes_summary(message_id, session)


def refund_prediction(message_id: int):
    with make_session() as session, session.begin():
        prediction = session.get(Prediction, message_id)
        if prediction is None:
            raise ValueError(f"could not find prediction attached to {message_id=}")
        if prediction.status == PredictionStatus.PAID:
            return "prediction has already been paid out"
        if prediction.status != PredictionStatus.CLOSED:
            raise ValueError(f"prediction attached to {message_id=} is not closed")

        votes = session.scalars(
            select(PredictionVote).where(PredictionVote.prediction == message_id)
        ).all()

        for vote in votes:
            add_points_to_user(
                vote.user_id, vote.amount, reason=f"prediction {message_id} refund"
            )
        prediction.status = PredictionStatus.REFUNDED
        return get_votes_summary(message_id, session)
