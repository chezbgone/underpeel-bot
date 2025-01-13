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
