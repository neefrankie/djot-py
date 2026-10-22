from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
import re
from typing import Any, Generic, List, Optional, TypeVar

from djot.input import InputText
from djot.inline import InlineParser
from djot.event import (
    Event,
)
from djot.common import Range

from djot.common.list_style import ListStyle

from .container import ContainerCap


@dataclass(slots=True)
class HeadingData:
    level: int

@dataclass(slots=True)
class FootnoteData:
    label: str
    indent: int

@dataclass(slots=True)
class RefDefData:
    key: str
    indent: int

@dataclass(slots=True)
class ListData:
    styles: List[ListStyle]
    indent: int

@dataclass(slots=True)
class TableData:
    columns: int

@dataclass(slots=True)
class FencedDivData:
    colons: int

@dataclass(slots=True)
class CodeBlockData:
    close_pattern: re.Pattern

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

T = TypeVar('T')

@dataclass
class BlockFrame(Generic[T]):
    rule: 'BlockRule'
    start_pos: int = 0 # snapshot of cursor position the moment this container is created.
    closing_boundary: Optional[Range] = None # the position of closing token.
    indent: Optional[int] = None
    data: Optional[T] = None
    inline_parser: Optional[InlineParser] = None

    def update_closing_boundary(self, start: int, end: int):
        self.closing_boundary = Range(start, end)
    

    def __repr__(self) -> str:
        return f'Container<{self.rule.__class__.__name__}>'

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

    def on_continue(self, ctx: ParsingContext) -> 'ContinueResult':
        return self.rule.on_continue(self, ctx)

    def on_close(self, ctx: ParsingContext) -> List[Event]:
        return self.rule.on_close(self, ctx)
        

class OpenStatus(Enum):
    MATCHED = auto() # A rule applied successfully, so stop trying the rest of rules.
    NOT_MATCHED = auto() # Current rule does not apply to a block, continue to try next rules.
    FALLBACK = auto() # Syntax error, fallback to paragraph rule.
    MATCH_AND_CONSUMED = auto() # A rule applied successfully and consumed the whole line, so stop trying any rules and jump to next line directly.

    CLOSE = auto() # a container should be closed.
    
class ContinueAction(Enum):
    """
    Determine the lifecycle of a frame.
    
    CONTINUE: continue to inner frames.
    STOP: stop searcing for inner frames and all frames from here
    to the end should be closed.
    """
    CONTINUE = auto()
    STOP = auto()
    CLOSE = auto()



@dataclass
class OpenResult:
    """Data carried out after applying each rule.
    
    Attributes:
        status: The state of open/continue/close is more than a simple boolean couls express.
        events: the events generated in a rule's operation
        container: Open operation usually creates a new container. However, continue/close operation could fallback to a new container.
        finished_line: Flag indicating whether an operation gobbles the whole line so that we stop early.
    """
    status: OpenStatus
    events: List[Event] = field(default_factory=list)
    frame: Optional[BlockFrame[Any]] = None
    def __repr__(self) -> str:
        return f'RuleResult(status={self.status.name}, new events: {len(self.events)}, new container: {self.frame})'

    @classmethod
    def not_matched(cls) -> 'OpenResult':
        return cls(status=OpenStatus.NOT_MATCHED)


class LineAction(Enum):
    """
    Whether a line is consume in continue operation.
    For CONSUMED, circirt-break and to to next line directly.
    """
    PROCEED = auto()
    CONSUMED = auto()

@dataclass(slots=True, frozen=True)
class ContinueResult:
    """
    This differs from OpenResult in term of line finished.
    ContinueAction determines the lifecycle of a frame.
    A frame could be allowed to continue while it consumed
    the whole line since a frame may cover multiple lines,
    or it could be terminateded while consumed the whole line.
    """
    action: ContinueAction # determin the lifecycle of frame.
    # Mode rules do not generate event during on continue phase.
    # There are two exceptions: reference definition and table.
    events: List[Event] = field(default_factory=list)
    line_action: LineAction = LineAction.PROCEED

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
    def try_open(self, cursor: InputText) -> OpenResult:
        pass

    @abstractmethod
    def on_continue(self, frame: BlockFrame, ctx: ParsingContext) -> ContinueResult:
        pass

    @abstractmethod
    def on_close(self, frame: BlockFrame, ctx: ParsingContext) -> List[Event]:
        pass