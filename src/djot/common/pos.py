from dataclasses import dataclass


@dataclass
class SourceLoc:
    line: int
    col: int
    offset: int

    def __str__(self) -> str:
        return f'{self.line}:{self.col}:{self.offset}'

@dataclass
class Pos:
    start: SourceLoc
    end: SourceLoc

    def __str__(self) -> str:
        return f'{self.start} - {self.end}'