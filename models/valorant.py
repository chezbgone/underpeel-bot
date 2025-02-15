from dataclasses import dataclass
from urllib.parse import quote
from typing import ClassVar, Literal, Self, final

import database.models as db


@dataclass(frozen=True)
class RiotId:
    game_name: str
    tagline: str

    @classmethod
    def from_db(cls, riot_id: db.RiotId) -> Self:
        return cls(riot_id.game_name, riot_id.tagline)

    @classmethod
    def maybe_from_db(cls, riot_id: db.RiotId | None) -> Self | None:
        if riot_id is None:
            return None
        return cls(riot_id.game_name, riot_id.tagline)

    def __str__(self) -> str:
        return f"{self.game_name}#{self.tagline}"

    def tracker(self, style=True) -> str:
        url_base = "https://tracker.gg/valorant/profile/riot"
        path = quote(f"{self.game_name}#{self.tagline}")
        link = f"{url_base}/{path}"
        if style:
            return f"[{str(self)}]({link})"
        return link


@final
@dataclass(frozen=True)
class SimpleRank:
    tier: Literal[
        "Iron",
        "Bronze",
        "Silver",
        "Gold",
        "Platinum",
        "Diamond",
        "Ascendant",
    ]
    division: Literal[1, 2, 3]

    @classmethod
    def try_from(cls, rank_str: str) -> Self | None:
        match rank_str.split():
            case [
                (
                    "Iron"
                    | "Bronze"
                    | "Silver"
                    | "Gold"
                    | "Platinum"
                    | "Diamond"
                    | "Ascendant"
                ) as tier,
                ("1" | "2" | "3") as division,
            ]:
                return cls(tier, int(division))  # type: ignore
            case _:
                return None

    def __str__(self) -> str:
        return f"{self.tier} {self.division}"


@final
@dataclass
class ImmortalPlus:
    name: Literal[
        "Immortal 1",
        "Immortal 2",
        "Immortal 3",
        "Radiant",
    ]

    possible_names: ClassVar[list[str]] = []

    @classmethod
    def try_from(cls, rank_str) -> Self | None:
        match rank_str:
            case "Immortal 1" | "Immortal 2" | "Immortal 3" | "Radiant":
                return cls(rank_str)

    def __str__(self) -> str:
        return self.name
