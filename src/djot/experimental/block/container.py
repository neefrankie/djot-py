from enum import Enum, auto
from typing import List, NamedTuple

from djot.common import ListStyle


class ContainerCap(Enum):
    NONE = auto()
    INLINE = auto()
    BLOCK = auto()
    TEXT = auto()
    CELLS = auto()
    ATTRIBUTES = auto()
    LIST_ITEM = auto()


class FootnoteData(NamedTuple):
    label: str
    indent: int

class RefDefData(NamedTuple):
    key: str
    indent: int

class ListData(NamedTuple):
    styles: List[ListStyle]
    indent: int