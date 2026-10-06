from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
import re
from typing import Any, Generic, List, Optional, TypeVar

from ..input import InputText
from ..inline import InlineParser
from ..attributes import AttributeParser, AttrFlowControl
from ..event import (
    Event,
)
from ..common import Range


# In djot.js, this is called ContentType.
class ContainerCap(Enum):
    NONE = auto()
    INLINE = auto()
    BLOCK = auto()
    TEXT = auto()
    CELLS = auto()
    ATTRIBUTES = auto()
    LIST_ITEM = auto()

@dataclass
class HeadingData:
    level: int

@dataclass
class FootnoteData:
    label: str
    indent: int

@dataclass
class RefDefData:
    key: str
    indent: int

@dataclass
class ListData:
    styles: List[str]
    indent: int

@dataclass
class TableData:
    columns: int

@dataclass
class FencedDivData:
    colons: int

@dataclass
class CodeBlockData:
    close_pattern: re.Pattern

@dataclass
class AttributeData:
    status: AttrFlowControl
    indent: int
    startpos: int
    spans: List[Range]

@dataclass(frozen=True)
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
    cursor: InputText
    is_covered: bool = False
    last_span_end: Optional[int] = None

T = TypeVar('T')

@dataclass
class Container(Generic[T]):
    rule: 'BlockRule'
    start_pos: int = 0 # snapshot of cursor position the moment this container is created.
    closing_boundary: Optional[Range] = None # the position of closing token.
    indent: Optional[int] = None
    data: Optional[T] = None
    inline_parser: Optional[InlineParser] = None
    attribute_parser: Optional[AttributeParser] = None # parse block attributes

    def update_closing_boundary(self, start: int, end: int):
        self.closing_boundary = Range(start, end)
    

    def __repr__(self) -> str:
        return f'Container<{self.rule.__class__.__name__}>'

    @property
    def node_type(self) -> ContainerCap:
        return self.rule.kind

    @property
    def children_type(self) -> ContainerCap:
        return self.rule.accepts_content

    @property
    def accepts_block(self) -> bool:
        return self.rule.accepts_blocks()

    @property
    def accepts_raw_text(self):
        return self.children_type == ContainerCap.TEXT

    def can_cantain(self, other: 'Container') -> bool:
        return self.children_type == other.node_type

    def can_nest(self, rule: 'BlockRule') -> bool:
        return self.rule.accepts_content == rule.kind

    def on_continue(self, ctx: ParsingContext) -> 'RuleResult':
        return self.rule.on_continue(self, ctx)

    def on_close(self, ctx: ParsingContext) -> 'RuleResult':
        return self.rule.on_close(self, ctx)
        

class FlowControl(Enum):
    OPEN = auto()
    CONTINUE = auto()
    STOP = auto() # stop searching deeper in a node path.
    CLOSE = auto() # a container should be closed.
    FAIL = auto()


@dataclass
class RuleResult:
    """Data carried out after applying each rule.
    
    Attributes:
        status: The state of open/continue/close is more than a simple boolean couls express.
        events: the events generated in a rule's operation
        container: Open operation usually creates a new container. However, continue/close operation could fallback to a new container.
        finished_line: Flag indicating whether an operation gobbles the whole line so that we stop early.
    """
    status: FlowControl
    events: List[Event] = field(default_factory=list)
    container: Optional[Container[Any]] = None
    finished_line: bool = False
    next_pos: Optional[int] = None

    def __repr__(self) -> str:
        return f'RuleResult(status={self.status.name}, new events: {len(self.events)}, new container: {self.container}, finished_line={self.finished_line})'

    @property
    def is_continue(self) -> bool:
        return self.status == FlowControl.CONTINUE

    @property
    def is_open(self) -> bool:
        return self.status == FlowControl.OPEN

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
        finished_line: bool = False
    ) -> 'RuleResult':
        return cls(
            status=FlowControl.CONTINUE,
            events=events or [],
            finished_line=finished_line,
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
    def try_open(self, cursor: InputText) -> RuleResult:
        pass

    @abstractmethod
    def on_continue(self, container: Container, ctx: ParsingContext) -> RuleResult:
        pass

    @abstractmethod
    def on_close(self, container: Container, ctx: ParsingContext) -> RuleResult:
        pass