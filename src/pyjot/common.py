from dataclasses import dataclass
from enum import Enum
from typing import List


@dataclass
class Range:
    __slots__ = ('start', 'end')
    start: int
    end: int

@dataclass
class MatchedRange(Range):
    captures: List[str]
    
class ParseStatus(Enum):
    DONE = 0
    FAIL = 1
    CONTINUE = 2


@dataclass
class SourceLoc:
    line: int
    col: int
    offset: int

