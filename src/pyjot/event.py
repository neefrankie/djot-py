from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Union

from .common import Range

class Action(Enum):
    ENTER = auto()
    EXIT = auto()

class VerbatimKind(Enum):
    DISPLAY_MATH = auto() # +/-
    INLINE_MATH = auto() # +/-
    VERBATIM = auto() # +/-

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

class LeafKind(Enum):
    BLANKLINE = auto()
    CHECKBOX = auto()
    CODE_LANGUAGE = auto()
    ELLIPSES = auto()
    EM_DASH = auto()
    EN_DASH = auto()
    ESCAPE = auto()
    FOOTNOTE_REF = auto()
    HARD_BREAK = auto()
    IMAGE_MARKER = auto()
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

class InlineContainer(Enum):
    SUBSCRIPT = auto() # +/-
    SUPERSCRIPT = auto() # +/-
    EMPH = auto() # _ _
    STRONG = auto() # * *
    INSERT = auto() # {+ +}
    DELETE = auto() # {- -}
    MARK = auto() # {= =}
    SINGLE_QUOTED = auto() # '  '
    DOUBLE_QUOTED = auto() # "  "

class InlineLeaf(Enum):
    STR = auto()
    LEFT_SINGLE_QUOTE = auto()
    RIGHT_SINGLE_QUOTE = auto()
    LEFT_DOUBLE_QUOTE = auto()
    RIGHT_DOUBLE_QUOTE = auto()


# Atributes are all leaves.
class AttrKind(Enum):
    COMMENT = auto()
    CLASS = auto()
    CLASS_START = auto()
    EQUAL_MARKER = auto()
    ID = auto()
    ID_START = auto()
    KEY = auto()
    QUOTE_MARKER = auto()
    SPACE = auto()
    VALUE = auto()
    

class Alignment(Enum):
    DEFAULT = auto()
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()

EventKind = Union[
    ContainerKind,
    LeafKind,
    VerbatimKind,
    InlineContainer,
    InlineLeaf,
    AttrKind,
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

    @property
    def is_open_marker(self) -> bool:
        return self.kind == LeafKind.OPEN_MARKER

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
    def enter(cls, span: Range, kind: ContainerKind | VerbatimKind | InlineContainer) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=Action.ENTER
        )

    @classmethod
    def exit(cls, span: Range, kind: ContainerKind | VerbatimKind | InlineContainer) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=Action.EXIT
        )

    @classmethod
    def leaf(cls, span: Range, kind: LeafKind | InlineLeaf) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=None
        )

    @classmethod
    def attr(cls, span: Range, kind: AttrKind) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=None
        )


@dataclass(slots=True)
class ListEvent(Event):
    styles: List[str] = field(default_factory=list)


