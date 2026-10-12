from dataclasses import dataclass


@dataclass(slots=True)
class Range:
    start: int
    end: int

    def __str__(self) -> str:
        return f'{self.start}:{self.end}'