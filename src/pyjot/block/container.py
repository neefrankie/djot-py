from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
import re
from typing import Any, Generic, List, Optional, TypeVar

from ..input import InputText
from ..inline import InlineParser
from ..attributes import AttributeParser
from ..event import (
    Event,
)
from ..common import Range, ParseStatus


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
    span: Optional[Range]

@dataclass
class CodeBlockData:
    close_pattern: re.Pattern
    span: Optional[Range] = None

@dataclass
class AttributeData:
    status: ParseStatus
    indent: int
    startpos: int
    spans: List[Range]

T = TypeVar('T')

@dataclass
class Container(Generic[T]):
    rule: 'BlockRule'
    indent: Optional[int] = None
    inline_parser: Optional[InlineParser] = None
    attribute_parser: Optional[AttributeParser] = None
    data: Optional[T] = None

    @property
    def node_type(self) -> ContainerCap:
        return self.rule.kind

    @property
    def children_type(self) -> ContainerCap:
        return self.rule.accepts_content

    @property
    def can_child_be_block(self) -> bool:
        return self.rule.accepts_blocks()

    def can_nest(self, other: 'Container') -> bool:
        return self.children_type == other.node_type

    def allow_nest(self, rule: 'BlockRule') -> bool:
        return self.children_type == rule.kind

    def try_continue(self, cursor: InputText) -> 'RuleResult':
        return self.rule.try_continue(cursor, self)

    def close(self, cursor: InputText, last_span_end: Optional[int]) -> 'RuleResult':
        events: List[Event] = []
        if self.inline_parser:
            events.extend(self.inline_parser.iter_merged_events())
        result = self.rule.on_close(cursor, self, last_span_end)
        result.events = events + result.events
        return result
        

class FlowControl(Enum):
    OPEN = auto()
    CONTINUE = auto()
    CLOSE = auto()
    FAIL = auto()
    FALLBACK = auto()


@dataclass
class RuleResult:
    """Data carried out after applying each rule.
    
    Attributes:
        status: The state of open/continue/close is more than a simple boolean couls express.
        events: the events generated in a rule's operation
        container: Open operation usually creates a new container. However, continue/close operation could fallback to a new container.
        finished_line: Flag indicating whether an operation gobbles the whole line so that we stop early.

    Cases of result returned
    ------------------------
    
    
    """
    status: FlowControl
    events: List[Event] = field(default_factory=list)
    container: Optional[Container[Any]] = None
    finished_line: bool = False

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
        accepts_content: what kind of nodes are allowed to be attached to current node..
    """
    kind: ContainerCap # 
    accepts_content: ContainerCap # 

    def can_be_root_or_nested(self, container: Optional[Container]) -> bool:
        """Whether current node can be root or be nested
        
        If there's no parent node, and current rule is block, then it can be a root node.
        If parent node exists, parent node's allowed children type must agree with current rule.
        """
        if not container:
            return ContainerCap.BLOCK == self.kind

        return self.kind == container.children_type

    def accepts_blocks(self) -> bool:
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
    def try_continue(self, cursor: InputText, container: Container) -> RuleResult:
        pass

    @abstractmethod
    def on_close(
        self, 
        cursor: InputText, 
        container: Container, 
        last_span_end: Optional[int]
    ) -> RuleResult:
        """关闭块，出栈并做收尾工作"""
        pass