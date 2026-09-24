from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Union

from .common import Range

class Action(Enum):
    ENTER = auto()
    EXIT = auto()

class BlockContainer(Enum):
    ATTRIBUTES = auto() # +/-
    ANNOTATION = auto() # +/-
    BLOCK_QUOTE = auto() # +/-
    CAPTION = auto() # +/-
    CODE_BLOCK = auto() # +/-
    DIV = auto() # +/-
    FENCED_DIV = auto() # +/-
    FOOTNOTE = auto() # +/-
    HEADING = auto() # +/-
    LIST = auto() # +/-
    LIST_ITEM = auto() # +/-
    REFERENCE_DEFINITION = auto() # +/-
    PARA = auto() # +/-
    TABLE = auto() # +/-
    TABLE_ROW = auto() # +/-
    TABLE_CELL = auto() # +/-

class BlockLeaf(Enum):
    BLANKLINE = auto()
    THEMATIC_BREAK = auto()
    TABLE_SEPARATOR = auto() # :---:

class VerbatimKind(Enum):
    DISPLAY_MATH = auto() # $$`...`
    INLINE_MATH = auto() # $`...`
    VERBATIM = auto() # `...`

class InlineContainer(Enum):
    DELETE = auto() # {- -}
    DESTINATION = auto() # ( )
    DOUBLE_QUOTED = auto() # "  "
    EMAIL = auto() # < >
    EMPH = auto() # _ _
    IMAGE_TEXT = auto() # [ ]
    LINK_TEXT = auto() # [ ]
    INSERT = auto() # {+ +}
    MARK = auto() # {= =}
    REFERENCE = auto() # [ ]
    SPAN = auto() # [ ]
    SINGLE_QUOTED = auto() # '  '
    SUBSCRIPT = auto() # +/-
    SUPERSCRIPT = auto() # +/-
    STRONG = auto() # * *
    URL = auto() # < >
    

class InlineLeaf(Enum):
    CHECKBOX = auto() # X
    CODE_LANGUAGE = auto()
    EM_DASH = auto() # ---
    EN_DASH = auto() # --
    ELLIPSES = auto() # ...
    ESCAPE = auto() # \
    FOOTNOTE_REF = auto() # [^foo]
    HARD_BREAK = auto() # \+\n
    IMAGE_MARKER = auto() # !
    LEFT_SINGLE_QUOTE = auto() # ', {'
    LEFT_DOUBLE_QUOTE = auto() # ", {"
    NBSP = auto() # \ + space
    NOTE_LABEL = auto() # foo inside [^foo]
    OPEN_MARKER = auto() # { in braced delimiter
    RAW_FORMAT = auto() # =FORMAT
    REFERENCE_KEY = auto() # reference link key [foo]: https://example.com
    REFERENCE_VALUE = auto() # reference link value
    RIGHT_SINGLE_QUOTE = auto() # ', '}
    RIGHT_DOUBLE_QUOTE = auto() # ", "}
    SOFT_BREAK = auto() # line break in inline content
    SYMBOL = auto() # smiley
    STR = auto()
    TABLE_SEPARATOR = auto() # :---:


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
    BlockContainer,
    BlockLeaf,
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
        return self.kind == InlineLeaf.STR

    @property
    def is_container(self) -> bool:
        return self.action is not None

    @property
    def is_leaf(self) -> bool:
        return self.action is None

    @property
    def is_open_marker(self) -> bool:
        return self.kind == InlineLeaf.OPEN_MARKER

    @property
    def is_soft_break(self) -> bool:
        return self.kind == InlineLeaf.SOFT_BREAK

    def with_list_styles(self, styles: List[str]):
        if self.kind != BlockContainer.LIST or self.kind != BlockContainer.LIST_ITEM:
            return self
        
        self.payload = ListPayload(
            styles=styles
        )
        return self

    def with_table_alignment(self, align: Alignment):
        if self.kind != InlineLeaf.TABLE_SEPARATOR:
            return self
        
        self.payload = TablePayload(
            alignment=align,
        )
        return self

    def with_checkbox(self, checked: bool):
        if self.kind != InlineLeaf.CHECKBOX:
            return self
        
        self.payload = CheckboxPayload(
            checked=checked,
        )
        return self

    def demote_to_str(self):
        self.kind = InlineLeaf.STR
        self.action = None

    def expand(self, other: 'Event') -> bool:
        """Merge consecutive same leaf."""
        if self.kind == other.kind and self.span.end + 1 == other.span.start and self.action is None and other.action is None:
            self.span.end = other.span.end
            return True

        return False

    @classmethod
    def enter(cls, span: Range, kind: BlockContainer | VerbatimKind | InlineContainer) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=Action.ENTER
        )

    @classmethod
    def exit(cls, span: Range, kind: BlockContainer | VerbatimKind | InlineContainer) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=Action.EXIT
        )

    @classmethod
    def leaf(cls, span: Range, kind: BlockLeaf | InlineLeaf) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=None
        )

    @classmethod
    def str(cls, startpos: int, endpos: int) -> 'Event':
        return cls(
            span=Range(startpos, endpos),
            kind=InlineLeaf.STR,
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


