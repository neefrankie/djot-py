from dataclasses import dataclass


@dataclass
class Event:
    startpos: int
    endpos: int
    annot: str