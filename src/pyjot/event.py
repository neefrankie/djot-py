from abc import ABC
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List

from .common import Range

class Action(Enum):
    NONE = auto()
    ENTER = auto()
    EXIT = auto()

class ContainerKind(Enum):
    ANNOTATION = auto() # +/-
    BLOCK_QUOTE = auto() # +/-
    CAPTION = auto() # +/-
    CODE_BLOCK = auto() # +/-
    DESTINATION = auto() # +/-
    DISPLAY_MATH = auto() # +/-
    DIV = auto() # +/-
    EMAIL = auto() # +/-
    FENCED_DIV = auto() # +/-
    FOOTNOTE = auto() # +/-
    HEADING = auto() # +/-
    IMAGE_TEXT = auto() # +/-
    INLINE_MATH = auto() # +/-
    LINK_TEXT = auto() # +/-
    LIST = auto() # +/-
    LIST_ITEM = auto() # +/-
    REFERENCE_DEFINITION = auto() # +/-
    REFERENCE = auto() # +/-
    SPAN = auto() # +/-
    PARA = auto() # +/-
    TABLE = auto() # +/-
    TABLE_ROW = auto() # +/-
    TABLE_CELL = auto() # +/-
    URL = auto() # +/-
    VERBATIM = auto() # +/-


class LeafKind(Enum):
    ATTR_SPACE = auto()
    ATTR_ID_START = auto()
    ATTR_CLASS_START = auto()
    ATTR_EQUAL_MARKER = auto()
    ATTR_QUOTE_MARKER = auto()
    ATTRIBUTE = auto()
    BLANKLINE = auto()
    CHECKBOX = auto()
    CLASS = auto()
    CODE_LANGUAGE = auto()
    COMMENT = auto()
    ELLIPSES = auto()
    EM_DASH = auto()
    EN_DASH = auto()
    ESCAPE = auto()
    FOOTNOTE_REF = auto()
    HARD_BREAK = auto()
    ID = auto()
    IMAGE_MARKER = auto()
    KEY = auto()
    NBSP = auto()
    NOTE_LABEL = auto()
    RAW_FORMAT = auto()
    REFERENCE_KEY = auto()
    REFERENCE_VALUE = auto()
    SOFT_BREAK = auto()
    STR = auto()
    SYMBOL = auto()
    THEMATIC_BREAK = auto()
    TABLE_SEPARATOR = auto()
    VALUE = auto()

class Alignment(Enum):
    DEFAULT = auto()
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()

@dataclass(slots=True)
class Event(ABC):
    span: Range
    kind: ContainerKind | LeafKind

@dataclass(slots=True)
class TagEvent(Event):
    action: Action = Action.ENTER

    @classmethod
    def enter(cls, kind: ContainerKind, span: Range) -> 'TagEvent':
        return cls(
            action=Action.ENTER,
            kind=kind,
            span=span
        )

    @classmethod
    def exit(cls, kind: ContainerKind, span: Range) -> 'TagEvent':
        return cls(
            action=Action.EXIT,
            kind=kind,
            span=span,
        )

@dataclass(slots=True)
class ListEvent(TagEvent):
    styles: List[str] = field(default_factory=list)

@dataclass(slots=True)
class LeafEvent(Event):
    pass

@dataclass(slots=True)
class CheckboxEvent(LeafEvent):
    checked: bool
    kind: LeafKind | ContainerKind = LeafKind.CHECKBOX

@dataclass(slots=True)
class TableSeparatorEvent(LeafEvent):
    alignment: Alignment
    kind: LeafKind | ContainerKind = LeafKind.TABLE_SEPARATOR
