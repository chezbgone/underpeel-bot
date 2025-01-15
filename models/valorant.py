from dataclasses import dataclass

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
            return f'[{str(self)}]({url_base}/{self.game_name}%23{self.tagline})'
        return f'{url_base}/{self.game_name}%23{self.tagline}'


@dataclass(order=True)
class Rank:
    id: int
    name: str

    def __str__(self) -> str:
        return self.name
    
    def peelo(self) -> int:
        match self.id:
            case 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11: # Iron, Silver, Gold
                return 500
            case 24 | 25 | 26 | 27: # Immortal+
                return 10000000
            case k if k in range(12, 24):
                # 12 -> 900
                # 13 -> 1000
                return 100 * k - 300
        raise ValueError(self)

@dataclass
class ActInfo:
    name: str
    games_played: int
    peak_rank: Rank | None

    @classmethod
    def of(cls, season_json):
        short_name = season_json['season']['short']
        played = season_json['games']
        peak_data = max(
            season_json['act_wins'],
            default=None,
            key=lambda win: win['id'],
        )
        peak = None
        if peak_data is not None:
            peak = Rank(peak_data['id'], peak_data['name'])
        return ActInfo(short_name, played, peak)

    @classmethod
    def empty(cls, season_name: str):
        return ActInfo(season_name, 0, None)
    
    def display(self) -> str:
        return f'played {self.games_played}, peak {self.peak_rank}'

