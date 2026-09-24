from dataclasses import dataclass


@dataclass(slots=True)
class Range:
    start: int
    end: int

    def shrink_end(self, end: int):
        self.start = end

    def __str__(self) -> str:
        return f'{self.start}:{self.end}'

@dataclass(slots=True)
class SourceLoc:
    line: int
    col: int
    offset: int

