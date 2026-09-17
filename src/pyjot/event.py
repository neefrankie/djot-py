from abc import ABC
from dataclasses import dataclass
from enum import Enum, auto
from typing import List

from .common import Range

class Action(Enum):
    NONE = auto()
    ENTER = auto()
    EXIT = auto()

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

    ANNOTATION = auto()
    DISPLAY_MATH = auto()
    INLINE_MATH = auto()
    VERBATIM = auto()
    RAW_FORMAT = auto()
    ESCAPE = auto()
    HARD_BREAK = auto()
    SOFT_BREAK = auto()
    NBSP = auto()
    EMAIL = auto()
    URL = auto()
    OPEN_MARKER = auto()
    SYMBOL = auto()
    ELLIPSES = auto()
    FOOTNOTE_REF = auto()
    IMAGE_MARKER = auto()
    IMAGE_TEXT = auto()
    LINK_TEXT = auto()
    REFERENCE = auto()
    SPAN = auto()
    DESTINATION = auto()
    EM_DASH = auto()
    EN_DASH = auto()

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
    kind: ElementKind # TODO: can we simply use AstNode?
    span: Range
    payload: EventPayload | None = None

    @classmethod
    def new(cls, start: int, end: int, kind: ElementKind):
        return cls(
            action=Action.NONE,
            kind=kind,
            span=Range(start=start, end=end)
        )

    @classmethod
    def enter(cls, start: int, end: int, kind: ElementKind, ):
        return cls(
            action=Action.ENTER,
            kind=kind,
            span=Range(start=start, end=end)
        )

    @classmethod
    def exit(cls, start: int, end: int, kind: ElementKind):
        return cls(
            action=Action.EXIT,
            kind=kind,
            span=Range(start=start, end=end)
        )

@dataclass
class Element(ABC):
    pass

@dataclass
class ParaElement(Element):
    pass

@dataclass
class CheckboxElement(Element):
    checked: bool

@dataclass
class EventKind(ABC):
    element: Element

@dataclass
class EventEnter(EventKind): # for + sign
    pass

@dataclass
class EventExit(EventKind): # for - sign
    pass

@dataclass
class EventEmpty(EventKind): # no sign
    pass

@dataclass
class EventV2:
    kind: EventKind
    span: Range