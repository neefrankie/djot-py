from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Union

from .common import Range

class Action(Enum):
    ENTER = auto()
    EXIT = auto()

class ContainerKind(Enum):
    ATTRIBUTES = auto() # +/-
    ANNOTATION = auto() # +/-
    BLOCK_QUOTE = auto() # +/-
    CAPTION = auto() # +/-
    CODE_BLOCK = auto() # +/-
    DESTINATION = auto() # +/-
    DIV = auto() # +/-
    EMAIL = auto() # +/-
    FENCED_DIV = auto() # +/-
    FOOTNOTE = auto() # +/-
    HEADING = auto() # +/-
    IMAGE_TEXT = auto() # +/-
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

class VerbatimKind(Enum):
    DISPLAY_MATH = auto() # +/-
    INLINE_MATH = auto() # +/-
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
    OPEN_MARKER = auto()
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

EventKind = Union[
    ContainerKind,
    LeafKind,
    VerbatimKind
]

@dataclass(slots=True)
class ListPayload:
    styles: List[str]

@dataclass(slots=True)
class TablePayload:
    alignment: Alignment

@dataclass(slots=True)
class CheckboxPayload:
    checked: bool

Payload = Union[
    ListPayload,
    TablePayload,
    CheckboxPayload,
]

@dataclass(slots=True)
class Event:
    span: Range
    kind: EventKind
    action: Optional[Action]
    payload: Optional[Payload] = None

    @property
    def is_str(self) -> bool:
        return self.kind == LeafKind.STR

    @property
    def is_container(self) -> bool:
        return self.action is not None

    @property
    def is_leaf(self) -> bool:
        return self.action is None

    def with_list_styles(self, styles: List[str]):
        if self.kind != ContainerKind.LIST or self.kind != ContainerKind.LIST_ITEM:
            return self
        
        self.payload = ListPayload(
            styles=styles
        )
        return self

    def with_table_alignment(self, align: Alignment):
        if self.kind != LeafKind.TABLE_SEPARATOR:
            return self
        
        self.payload = TablePayload(
            alignment=align,
        )
        return self

    def with_checkbox(self, checked: bool):
        if self.kind != LeafKind.CHECKBOX:
            return self
        
        self.payload = CheckboxPayload(
            checked=checked,
        )
        return self

    def demote_to_str(self):
        self.kind = LeafKind.STR
        self.action = None

    def expand(self, other: 'Event') -> bool:
        """Merge consecutive same leaf."""
        if self.kind == other.kind and self.span.end + 1 == other.span.start and self.action is None and other.action is None:
            self.span.end = other.span.end
            return True

        return False

    @classmethod
    def enter(cls, span: Range, kind: ContainerKind | VerbatimKind) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=Action.ENTER
        )

    @classmethod
    def exit(cls, span: Range, kind: ContainerKind | VerbatimKind) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=Action.EXIT
        )

    @classmethod
    def leaf(cls, span: Range, kind: LeafKind) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=None
        )


@dataclass(slots=True)
class ListEvent(Event):
    styles: List[str] = field(default_factory=list)


