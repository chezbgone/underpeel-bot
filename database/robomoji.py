import logging
from datetime import datetime
from typing import Literal, Sequence

from sqlalchemy import select

from database import make_session, RobomojiInfo, Robomoji, RobomojiTransaction
from database.models import RobomojiTransactionKind

LOG = logging.getLogger(__name__)


def get_emoji_changes(user_id: int, limit=15) -> Sequence[RobomojiTransaction]:
    with make_session() as session:
        return session.scalars(
            select(RobomojiTransaction)
            .where(RobomojiTransaction.chatter_id == user_id)
            .order_by(RobomojiTransaction.time)
            .limit(limit)
        ).all()


def get_emoji_info(user_id: int) -> RobomojiInfo | None:
    with make_session() as session:
        return session.scalar(
            select(RobomojiInfo).where(RobomojiInfo.user_id == user_id)
        )


def register_emoji_use(user_id: int):
    with make_session() as session, session.begin():
        info = session.get(RobomojiInfo, user_id)
        if info is None:
            session.add(RobomojiInfo(user_id=user_id, last_reacted=datetime.now()))
            return
        info.last_reacted = datetime.now()


def toggle_emoji(
    staff_id: int | Literal["SYSTEM"],
    user_id: int,
    emoji: str,
    reason: str,
) -> RobomojiTransactionKind:
    with make_session() as session, session.begin():
        info = session.get(RobomojiInfo, user_id)
        if info is None:
            info = RobomojiInfo(user_id=user_id, last_reacted=datetime.min)
            session.add(info)
        robomojis = [] if info is None else info.robomojis

        for robomoji in robomojis:
            if robomoji.emoji == emoji:
                session.delete(robomoji)
                operation = RobomojiTransactionKind.REMOVED
                break
        else:
            new_robomoji = Robomoji(user_id=info.user_id, emoji=emoji)
            session.add(new_robomoji)
            operation = RobomojiTransactionKind.ADDED

        is_system = staff_id == "SYSTEM"
        session.add(
            RobomojiTransaction(
                chatter_id=user_id,
                emoji=emoji,
                time=datetime.now(),
                system=is_system,
                staff_id=(None if is_system else staff_id),
                reason=reason,
                action=operation,
            )
        )

    return operation
