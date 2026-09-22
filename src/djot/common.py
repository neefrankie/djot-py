from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class Range:
    start: int
    end: int

    def shrink_end(self, end: int):
        self.start = end

@dataclass(slots=True)
class MatchedRange(Range):
    captures: List[str]

@dataclass(slots=True)
class SourceLoc:
    line: int
    col: int
    offset: int

