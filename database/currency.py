import logging

from sqlalchemy import insert, update
from database import make_session, CurrencyInfo

LOG = logging.getLogger(__name__)


def get_user_points(id: int) -> int:
    """
    Returns the amount of currency in chatter `id`'s wallet.
    """
    with make_session() as session:
        if (info := session.get(CurrencyInfo, id)) is None:
            return 0
        return info.amount


def add_points_to_user(id: int, amount: int) -> int:
    """
    Add `amount` currency to chatter `id`'s wallet.
    Returns the new amount the user has.
    """
    with make_session() as session, session.begin():
        if session.get(CurrencyInfo, id) is None:
            session.execute(insert(CurrencyInfo).values(user_id=id, amount=amount))
            return amount
        else:
            new_amount = session.scalar(
                update(CurrencyInfo)
                .where(CurrencyInfo.user_id == id)
                .values(amount=CurrencyInfo.amount + amount)
                .returning(CurrencyInfo.amount)
            )
            assert new_amount is not None
            return new_amount
