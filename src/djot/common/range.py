from dataclasses import dataclass, field
from typing import List


@dataclass(slots=True)
class Range:
    start: int
    end: int

    def __str__(self) -> str:
        return f'{self.start}:{self.end}'

@dataclass(slots=True, frozen=True)
class MatchedRange:
    start: int
    end: int
    captures: List[str] = field(default_factory=list)