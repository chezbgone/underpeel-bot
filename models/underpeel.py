from dataclasses import dataclass


@dataclass(frozen=True)
class Player:
    discord_id: int
    peelo: int

@dataclass
class UnderpeelTeam:
    name: str
    tricode: str
    coach: int | None
    players: set[Player]

