import datetime
from dataclasses import dataclass
from typing import Literal


@dataclass
class RobomojiTransaction:
    time: datetime.datetime
    staff: int | Literal["SYSTEM"]
    chatter_id: int
    action: Literal["added", "removed"]
    emoji: str
    reason: str
