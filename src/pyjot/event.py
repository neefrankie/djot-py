from abc import ABC
from dataclasses import dataclass
from enum import Enum, auto
from typing import List

from .common import Range

class Action(Enum):
    NONE = auto()
    ENTER = auto()
    EXIT = auto()
    CHECKED = auto()
    UNCHECKED = auto()

class ElementKind(Enum):
    PARA = auto()
    BLOCK_QUOTE = auto()
    HEADING = auto()
    CAPTION = auto()
    FOOTNOTE = auto()
    NOTE_LABEL = auto()
    REFERENCE_DEFINITION = auto()
    REFERENCE_KEY = auto()
    REFERENCE_VALUE = auto()
    THEMATIC_BREAK = auto()
    LIST = auto()
    LIST_ITEM = auto()
    CHECKBOX = auto()
    TABLE = auto()
    TABLE_ROW = auto()
    TABLE_SEPARATOR = auto()
    TABLE_CELL = auto()
    ATTRIBUTE = auto()
    BLOCK_ATTRIBUTE = auto()
    FENCED_DIV = auto()
    CODE_BLOCK = auto()
    STR = auto()
    BLANKLINE = auto()

class EventPayload(ABC):
    pass

@dataclass
class ListPayload(EventPayload):
    styles: List[str]

@dataclass
class CheckboxPayload(EventPayload):
    checked: bool

class Alignment(Enum):
    DEFAULT = auto()
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()

@dataclass
class TableSepPayload(EventPayload):
    alignment: Alignment

@dataclass
class Event:
    action: Action
    kind: ElementKind
    span: Range
    payload: EventPayload | None = None