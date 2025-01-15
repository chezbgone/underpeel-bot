from dataclasses import dataclass

from aiohttp import ClientSession

from config import SECRETS
from models.valorant import ActInfo, Rank, RiotId

@dataclass
class Episode9Eligibility:
    a1: int
    a2: int
    a3: int
    peak: Rank

    @property
    def total_games(self):
        return self.a1 + self.a2 + self.a3

    def display(self):
        return (
            ':white_check_mark: '
            f'{self.a1} + {self.a2} + {self.a3} = {self.total_games} games in episode 9 '
            f'with peak {self.peak} ({self.peak.peelo()} peelo)'
        )

@dataclass
class Episode10Eligibility:
    games_played : int
    peak: Rank

    def display(self):
        return (
            ':white_check_mark: '
            f'{self.games_played} games in episode 10 act 1 '
            f'with peak {self.peak} ({self.peak.peelo()} peelo)'
        )

@dataclass
class NotEligible:
    def display(self):
        return f':x: Not enough games played.'

StatsEligibility = Episode9Eligibility | Episode10Eligibility | NotEligible

@dataclass
class PlayerStats:
    e9a1: ActInfo
    e9a2: ActInfo
    e9a3: ActInfo
    e10a1: ActInfo

    @classmethod
    async def of(cls, riot_id: RiotId, http_session: ClientSession):
        url = f'https://api.henrikdev.xyz/valorant/v3/mmr/na/pc/{riot_id.game_name}/{riot_id.tag}'
        headers = { 'Authorization': SECRETS['HENRIKDEV_KEY'] }
        async with http_session.get(url, headers=headers) as response:
            res = await response.json()
            seasons = res['data']['seasonal']
            season_dict: dict[str, ActInfo] = {
                season['season']['short']: ActInfo.of(season)
                for season in seasons
            }
            return PlayerStats(
                e9a1=season_dict.get('e9a1', ActInfo.empty('e9a1')),
                e9a2=season_dict.get('e9a2', ActInfo.empty('e9a2')),
                e9a3=season_dict.get('e9a3', ActInfo.empty('e9a3')),
                e10a1=season_dict.get('e10a1', ActInfo.empty('e10a1')),
            )
    
    def eligibility(self) -> StatsEligibility:
        acts = [self.e9a1, self.e9a2, self.e9a3]
        games = [act.games_played for act in acts]
        if sum(games) >= 75:
            a1, a2, a3 = games
            # fails if player somehow lost all 50 games
            peak = max(peak for act in acts if (peak := act.peak_rank) is not None)
            return Episode9Eligibility(a1, a2, a3, peak)
        if self.e10a1.games_played >= 50:
            # fails if player somehow lost all 50 games
            assert(self.e10a1.peak_rank is not None)
            return Episode10Eligibility(self.e10a1.games_played, self.e10a1.peak_rank)
        return NotEligible()
