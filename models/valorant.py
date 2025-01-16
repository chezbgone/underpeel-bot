from dataclasses import dataclass
from typing import Literal, Self
from urllib.parse import quote

@dataclass(frozen=True)
class RiotId:
    game_name: str
    tagline: str

    @property
    def tag(self) -> str:
        return self.tagline

    def __str__(self) -> str:
        return f'{self.game_name}#{self.tag}'
    
    def tracker(self, style=True) -> str:
        url_base = 'https://tracker.gg/valorant/profile/riot'
        if style:
            return f'[{str(self)}]({url_base}/{quote(self.game_name)}%23{self.tagline})'
        return f'{url_base}/{self.game_name}%23{self.tagline}'

@dataclass(frozen=True)
class SimpleRank:
    tier: Literal[
        'Iron',
        'Bronze',
        'Silver',
        'Gold',
        'Platinum',
        'Diamond',
        'Ascendant',
    ]
    division: Literal[1, 2, 3]

    @classmethod
    def try_from(cls, rank: str) -> Self | None:
        match rank.split():
            case [
                ('Iron' | 'Bronze' | 'Silver' | 'Gold' | 'Platinum' | 'Diamond' | 'Ascendant') as tier,
                ('1' | '2' | '3') as division,
            ]:
                return cls(tier, int(division))  # type: ignore
            case _:
                return None

    def __str__(self) -> str:
        return f'{self.tier} {self.division}'

    def peelo(self) -> int:
        match self.tier:
            case 'Iron' | 'Bronze' | 'Silver':
                return 500
            case 'Gold':
                return 800 + 100 * self.division
            case 'Platinum':
                return 1100 + 100 * self.division
            case 'Diamond':
                return 1400 + 100 * self.division
            case 'Ascendant':
                return 1700 + 100 * self.division

@dataclass
class ImmortalPlus:
    name: str
    rr: int | None

    def __str__(self) -> str:
        if self.rr is None:
            return f'{self.name} Unknown RR'
        return f'{self.name} {self.rr} RR'

    def peelo(self) -> int | None:
        if self.rr is None:
            return None
        return 2100 + 2 * self.rr

type Rank = None | SimpleRank | ImmortalPlus

def rank_sort_key(rank: Rank) -> int:
    match rank:
        case SimpleRank():
            return rank.peelo()
        case ImmortalPlus() as imm:
            if (peelo := imm.peelo()) is None:
                return 0
            return peelo
        case _:
            return 0

@dataclass
class ActInfo:
    name: str
    games_played: int
    peak_rank: Rank

    @classmethod
    def empty(cls, season_name: str):
        return ActInfo(season_name, 0, None)
    
    def display(self) -> str:
        return f'played {self.games_played}, peak {self.peak_rank}'
