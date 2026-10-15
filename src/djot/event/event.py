from dataclasses import dataclass
from typing import List, Optional, Union

from djot.common import (
    Range,
    Alignment,
    ListStyle
)

from .kind import (
    InlineLeaf,
    BlockLeaf,
    BlockContainer,
    EventKind,
    Action,
    VerbatimKind,
    InlineContainer,
    AttrKind
)


@dataclass(slots=True)
class ListPayload:
    styles: List[ListStyle]
    

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

    def __repr__(self) -> str:
        return f'Event(span=({self.span.start},{self.span.end}), kind={self.kind.name}, action={self.action.name if self.action else None}, payload={self.payload})'

    def __len__(self):
        return self.span.end - self.span.start + 1

    @property
    def startpos(self) -> int:
        return self.span.start

    @property
    def endpos(self) -> int:
        return self.span.end

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

    @property
    def is_blankline(self) -> bool:
        return self.kind == BlockLeaf.BLANKLINE

    def adjust_end(self, to: int):
        self.span.end = to

    def with_list_styles(self, styles: List[ListStyle]):
        if self.kind != BlockContainer.LIST and self.kind != BlockContainer.LIST_ITEM:
            return self
        
        self.payload = ListPayload(
            styles=styles,
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

    def switch_to_leaf(self, kind: InlineLeaf):
        self.kind = kind
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
    def table_sep(cls, startpos: int, endpos: int) -> 'Event':
        return cls(
            span=Range(startpos, endpos),
            kind=InlineLeaf.TABLE_SEPARATOR,
            action=None
        )

    @classmethod
    def escape(cls, startpos: int, endpos: int) -> 'Event':
        return cls(
            span=Range(startpos, endpos),
            kind=InlineLeaf.ESCAPE,
            action=None
        )

    @classmethod
    def nbsp(cls, startpos: int, endpos: int) -> 'Event':
        return cls(
            span=Range(startpos, endpos),
            kind=InlineLeaf.NBSP,
            action=None
        )

    @classmethod
    def hardbreak(cls, startpos: int, endpos: int) -> 'Event':
        return cls(
            span=Range(startpos, endpos),
            kind=InlineLeaf.HARD_BREAK,
            action=None
        )

    @classmethod
    def softbreak(cls, startpos: int, endpos: int) -> 'Event':
        return cls(
            span=Range(startpos, endpos),
            kind=InlineLeaf.SOFT_BREAK,
            action=None
        )

    @classmethod
    def blankline(cls, startpos: int, endpos: int) -> 'Event':
        return cls(
            span=Range(startpos, endpos),
            kind=BlockLeaf.BLANKLINE,
            action=None
        )

    @classmethod
    def attr(cls, span: Range, kind: AttrKind) -> 'Event':
        return cls(
            span=span,
            kind=kind,
            action=None
        )

    @classmethod
    def space(cls, start: int, end: int) -> 'Event':
        return cls(
            span=Range(start, end),
            kind=AttrKind.SPACE,
            action=None
        )