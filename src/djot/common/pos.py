from dataclasses import dataclass


@dataclass
class SourceLoc:
    line: int
    col: int
    offset: int

@dataclass
class Pos:
    start: SourceLoc
    end: SourceLoc