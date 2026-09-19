from dataclasses import dataclass
from enum import Enum
from typing import List


@dataclass(slots=True)
class Range:
    start: int
    end: int

@dataclass(slots=True)
class MatchedRange(Range):
    captures: List[str]

@dataclass(slots=True)
class SourceLoc:
    line: int
    col: int
    offset: int

