from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
import re
from typing import Generic, List, NamedTuple, Optional, TypeVar

from djot.inline import InlineParser
from djot.common import Range, ListStyle
from djot.event import Event

from ..attributes import AttributeParser

from ..cursor import LineContext, Cursor


class ContainerCap(Enum):
    NONE = auto()
    INLINE = auto()
    BLOCK = auto()
    TEXT = auto()
    CELLS = auto()
    ATTRIBUTES = auto()
    LIST_ITEM = auto()

@dataclass(slots=True, frozen=True)
class ParsingContext:
    """Data passed to a rule's methods
    
    Attributes:
        cursor: The input text and its current reading position
        is_covered: Is a container shadowned by innner container?
        last_span_end: last event's ending position
            
    NOTE:
        `is_covered` indicates top containers in a stack have higher precedence over a lower one. 
        For example, if a fenced div wraps code block, 
        the code block should claim the owership of any line starting with ::: rather than letting the containing fenced div to take it as ending markup.
    """
    cursor: Cursor
    line: LineContext
    is_covered: bool = False

class FootnoteData(NamedTuple):
    label: str
    indent: int

class RefDefData(NamedTuple):
    key: str
    indent: int

class ListData(NamedTuple):
    styles: List[ListStyle]
    indent: int

T = TypeVar('T')

@dataclass(slots=True)
class BlockFrame(Generic[T]):
    rule: 'BlockRule'
    start: LineContext # snapshot of cursor position the moment this frame is created.
    closing_boundary: Optional[Range] = None # the position of closing token.
    indent: Optional[int] = None # What's the purpose of this?
    inline_parser: Optional[InlineParser] = None
    attribute_parser: Optional[AttributeParser] = None # parse block attributes

    heading_level: Optional[int] = None
    footnote: Optional[FootnoteData] = None
    list_style: Optional[ListData] = None
    fenced_div_colons: Optional[int] = None
    code_block_close_pattern: Optional[re.Pattern] = None

    def update_closing_boundary(self, start: int, end: int):
        self.closing_boundary = Range(start, end)

    def __repr__(self) -> str:
            return f'Frame<{self.rule.__class__.__name__}>'

    @property
    def children_type(self) -> ContainerCap:
            return self.rule.accepts_content
    
    @property
    def accepts_block(self) -> bool:
        return self.rule.accepts_blocks()

    @property
    def accepts_raw_text(self):
        return self.rule.accepts_content == ContainerCap.TEXT

    def can_cantain(self, other: 'BlockFrame') -> bool:
        return self.rule.accepts_content == other.rule.kind

    def can_nest(self, rule: 'BlockRule') -> bool:
        return self.rule.accepts_content == rule.kind

    def on_continue(self, ctx: ParsingContext) -> 'RuleResult':
        return self.rule.on_continue(self, ctx)

    def on_close(self, ctx: ParsingContext) -> 'RuleResult':
        return self.rule.on_close(self, ctx)


class FlowControl(Enum):
    OPEN = auto()
    CONTINUE = auto()
    LINE_FINISHED = auto() # Go to next line directly.
    FALLBACK = auto() # Stop parsing current block, rewind, and yield to paragraph rule.
    STOP = auto() # stop searching deeper in a node path.
    CLOSE = auto() # a container should be closed.
    FAIL = auto()
    
@dataclass(slots=True)
class RuleResult:
    """Data carried out after applying each rule.
    
    Attributes:
        status: The state of open/continue/close is more than a simple boolean couls express.
        events: the events generated in a rule's operation
        container: Open operation usually creates a new container. However, continue/close operation could fallback to a new container.
        finished_line: Flag indicating whether an operation gobbles the whole line so that we stop early.
    """
    status: FlowControl
    events: List[Event] = field(default_factory=list) # events we could yield immediately.
    frame: Optional[BlockFrame] = None
    next_pos: Optional[LineContext] = None # position of next element in a line if status is open or continue.

    def __repr__(self) -> str:
        return f'RuleResult(status={self.status.name}, new events: {len(self.events)}, new frame: {self.frame})'

    @property
    def finished_line(self) -> bool:
        return self.status == FlowControl.LINE_FINISHED

    @property
    def is_continue(self) -> bool:
        return self.status == FlowControl.CONTINUE

    @property
    def is_open(self) -> bool:
        return self.status == FlowControl.OPEN or self.status == FlowControl.LINE_FINISHED

    @classmethod
    def open(cls) -> 'RuleResult':
        return RuleResult(
            status=FlowControl.OPEN
        )

    @classmethod
    def fail(cls) -> 'RuleResult':
        return cls(status=FlowControl.FAIL)

    @classmethod
    def continue_ok(
        cls, 
        events: Optional[List[Event]] = None, 
    ) -> 'RuleResult':
        return cls(
            status=FlowControl.CONTINUE,
            events=events or [],
        )

    @classmethod
    def close(cls) -> 'RuleResult':
        return cls(
            status=FlowControl.CLOSE,
        )

# In djot.js it is called BlockSpec.
@dataclass
class BlockRule(ABC):
    """Base class for element detection
    
    Attributes:
        kind: The type of current node in a tree.
        accepts_content: what kind of nodes are allowed to be attached to current node.

    NOTE:

    I think these two fields are actually describing a DAG,
    directed acyclic graph. `accepts_content` is an edge to children.
    However this is not a real a DAG, as it contains cyclic loop.
    """
    kind: ContainerCap
    accepts_content: ContainerCap

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.kind.name}->{self.accepts_content.name})'

    def can_be_root(self):
        """Whether current node can be root node or not.
                
        If there's no parent node, and current rule is block, then it can be a root node.
        """
        return self.kind == ContainerCap.BLOCK

    def accepts_blocks(self) -> bool:
        """Check if current rule could have block child"""
        return self.accepts_content in (ContainerCap.BLOCK, ContainerCap.LIST_ITEM)

    def accepts_inline_only(self) -> bool:
        return self.accepts_content == ContainerCap.INLINE

    def accepts_block_only(self) -> bool:
        return self.accepts_content == ContainerCap.BLOCK

    def accepts_text_only(self) -> bool:
        return self.accepts_content == ContainerCap.TEXT

    @abstractmethod
    def try_open(self, ctx: ParsingContext) -> RuleResult:
        pass

    @abstractmethod
    def on_continue(self, frame: BlockFrame, ctx: ParsingContext) -> RuleResult:
        pass

    @abstractmethod
    def on_close(self, frame: BlockFrame, ctx: ParsingContext) -> RuleResult:
        pass