import logging
from datetime import datetime

from sqlalchemy import insert, select, update
from database import make_session, CurrencyInfo, CurrencyTransaction

LOG = logging.getLogger(__name__)


def get_user_points(user_id: int) -> int:
    """
    Returns the amount of currency in chatter `id`'s wallet.
    """
    with make_session() as session:
        if (info := session.get(CurrencyInfo, user_id)) is None:
            return 0
        return info.amount


def add_points_to_user(user_id: int, amount: int, reason: str | None = None) -> int:
    """
    Add `amount` currency to chatter `id`'s wallet.
    Returns the new amount the user has.
    """
    with make_session() as session, session.begin():
        if session.get(CurrencyInfo, user_id) is None:
            session.execute(insert(CurrencyInfo).values(user_id=user_id, amount=amount))
            return amount
        new_amount = session.scalar(
            update(CurrencyInfo)
            .where(CurrencyInfo.user_id == user_id)
            .values(amount=CurrencyInfo.amount + amount)
            .returning(CurrencyInfo.amount)
        )
        assert new_amount is not None

        if reason is not None:
            session.add(
                CurrencyTransaction(
                    user_id=user_id,
                    time=datetime.now(),
                    delta=amount,
                    end_amount=new_amount,
                    reason=reason,
                )
            )

        return new_amount


def get_currency_transactions(user_id: int, limit: int = 15):
    with make_session() as session:
        return session.scalars(
            select(CurrencyTransaction)
            .where(CurrencyTransaction.user_id == user_id)
            .order_by(CurrencyTransaction.time.desc())
            .limit(limit)
        ).all()
