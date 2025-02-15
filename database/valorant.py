import logging

from database import make_session, RiotId

LOG = logging.getLogger(__name__)


def get_riot_id(user_id: int) -> RiotId | None:
    with make_session() as session:
        return session.get(RiotId, user_id)


def set_riot_id(user_id: int, game_name: str, tag: str):
    with make_session() as session, session.begin():
        session.merge(RiotId(user_id=user_id, game_name=game_name, tagline=tag))


def clear_riot_id(user_id: int):
    with make_session() as session, session.begin():
        item = session.get(RiotId, user_id)
        if item is not None:
            session.delete(item)
