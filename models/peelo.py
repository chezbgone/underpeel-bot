from dataclasses import dataclass

from models.valorant import ActInfo, ImmortalPlus, Rank, rank_sort_key

@dataclass
class Episode9Eligibility:
    a1: int
    a2: int
    a3: int
    peak: Rank

    @property
    def total_games(self):
        return self.a1 + self.a2 + self.a3

    def details(self):
        match self.peak:
            case None | ImmortalPlus(rr=None):
                peelo_description = '\n-# :warning: Need to calculate peelo manually.'
            case _:
                peelo_description = f' ({self.peak.peelo()} peelo)'
        return (
            ':white_check_mark: '
            f'{self.a1} + {self.a2} + {self.a3} = {self.total_games} games in episode 9 '
            f'with peak {self.peak}{peelo_description}'
        )

@dataclass
class Episode10Eligibility:
    games_played : int
    peak: Rank

    def details(self):
        match self.peak:
            case None | ImmortalPlus(rr=None):
                peelo_description = '\n-# :warning: Need to calculate peelo manually.'
            case _:
                peelo_description = f' ({self.peak.peelo()} peelo)'
        return (
            ':white_check_mark: '
            f'{self.games_played} games in episode 10 act 1 '
            f'with peak {self.peak}{peelo_description}'
        )

@dataclass
class NotEligible:
    def details(self):
        return f':x: Not enough games played.'

StatsEligibility = Episode9Eligibility | Episode10Eligibility | NotEligible

@dataclass
class PlayerStats:
    e9a1: ActInfo
    e9a2: ActInfo
    e9a3: ActInfo
    e10a1: ActInfo
    
    def eligibility(self) -> StatsEligibility:
        acts = [self.e9a1, self.e9a2, self.e9a3]
        games = [act.games_played for act in acts]
        if sum(games) >= 75:
            a1, a2, a3 = games
            peak = max((act.peak_rank for act in acts), key=rank_sort_key)
            return Episode9Eligibility(a1, a2, a3, peak)
        if self.e10a1.games_played >= 50:
            # fails if player somehow lost all 50 games
            assert(self.e10a1.peak_rank is not None)
            return Episode10Eligibility(self.e10a1.games_played, self.e10a1.peak_rank)
        return NotEligible()
