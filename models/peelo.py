from dataclasses import dataclass
from typing import final

from models.valorant import ImmortalPlus, SimpleRank


@final
@dataclass
class UnknownRank:
    def peelo(self):
        return None


Rank = SimpleRank | ImmortalPlus | UnknownRank


def rank_from_name(rank_name: str) -> Rank:
    if (rank := SimpleRank.try_from(rank_name)) is not None:
        return rank
    if (rank := ImmortalPlus.try_from(rank_name)) is not None:
        return rank
    return UnknownRank()


def rank_sort_key(rank: Rank) -> int:
    match rank:
        case UnknownRank():
            return 0
        case SimpleRank(tier, division):
            match tier:
                case "Iron":
                    return 0 + division
                case "Silver":
                    return 10 + division
                case "Bronze":
                    return 20 + division
                case "Gold":
                    return 30 + division
                case "Platinum":
                    return 40 + division
                case "Diamond":
                    return 50 + division
                case "Ascendant":
                    return 60 + division
        case ImmortalPlus(name):
            match name:
                case "Immortal 1":
                    return 100
                case "Immortal 2":
                    return 200
                case "Immortal 3":
                    return 300
                case "Radiant":
                    return 400


def peelo_of(rank: SimpleRank) -> int:
    match rank.tier:
        case "Iron" | "Bronze" | "Silver":
            return 500
        case "Gold":
            return 500 + 100 * rank.division
        case "Platinum":
            return 800 + 100 * rank.division
        case "Diamond":
            return 1100 + 100 * rank.division
        case "Ascendant":
            return 1400 + 200 * rank.division


def peelo_description(rank: Rank):
    match rank:
        case SimpleRank():
            return f" ({peelo_of(rank)} peelo)"
        case _:
            return "\n-# :warning: Need to calculate peelo manually."


@dataclass
class Episode10Eligibility:
    a1: int
    a2: int
    peak: Rank

    @property
    def total_games(self):
        return self.a1 + self.a2

    def details(self):
        return (
            ":white_check_mark: "
            f"{self.a1} + {self.a2} = {self.total_games} games in episode 10 "
            f"with peak {self.peak}{peelo_description(self.peak)}"
        )


@dataclass
class NotEligible:
    def details(self):
        return ":x: Not enough games played."


StatsEligibility = Episode10Eligibility | NotEligible


@dataclass
class ActInfo:
    name: str
    games_played: int
    peak_rank: Rank

    @classmethod
    def empty(cls, season_name: str):
        return ActInfo(season_name, 0, UnknownRank())

    def display(self) -> str:
        return f"played {self.games_played}, peak {self.peak_rank}"


@dataclass
class PlayerStats:
    e10a1: ActInfo
    e10a2: ActInfo

    def eligibility(self) -> StatsEligibility:
        acts = [self.e10a1, self.e10a2]
        games = [act.games_played for act in acts]
        if sum(games) >= 100:
            a1, a2 = games
            peaks = [act.peak_rank for act in acts if act.peak_rank is not None]
            peak = max(peaks, default=UnknownRank(), key=rank_sort_key)
            return Episode10Eligibility(a1, a2, peak)
        return NotEligible()
