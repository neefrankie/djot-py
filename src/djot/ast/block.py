from dataclasses import dataclass, field

from .base import (
    HasText,
    HasChildren,
    InlineNode,
    BlockNode,
    Caption,
)
from .list import (
    ListItem,
    OrderedListStyle,
    BulletListStyle,
    TaskListItem,
    DefinitionListItem,
)
from .table import (
    Row,
)

@dataclass(kw_only=True)
class Para(HasChildren[InlineNode], BlockNode):

    @property
    def tag(self) -> str:
        return 'para'

@dataclass(kw_only=True)
class Heading(HasChildren[InlineNode], BlockNode):
    level: int

    @property
    def tag(self) -> str:
        return 'heading'

@dataclass(kw_only=True)
class ThematicBreak(BlockNode):
    @property
    def tag(self) -> str:
        return 'thematic_break'

@dataclass(kw_only=True)
class Section(HasChildren[BlockNode], BlockNode):

    @property
    def tag(self) -> str:
        return 'section'

@dataclass(kw_only=True)
class Div(HasChildren[BlockNode], BlockNode):
    caption: Caption

    @property
    def tag(self) -> str:
        return 'div'



@dataclass(kw_only=True)
class CodeBlock(HasText, BlockNode):
    lang: str | None

    @property
    def tag(self) -> str:
        return 'code_block'

@dataclass(kw_only=True)
class RawBlock(HasText, BlockNode):
    format: str

    @property
    def tag(self) -> str:
        return 'raw_block'

@dataclass(kw_only=True)
class BlockQuote(HasChildren[BlockNode], BlockNode):

    @property
    def tag(self) -> str:
        return 'block_quote'

@dataclass(kw_only=True)
class OrderedList(HasChildren[ListItem], BlockNode):
    style: OrderedListStyle
    start: int | None
    loose: bool
    
    @property
    def tag(self) -> str:
        return 'ordered_list'

@dataclass(kw_only=True)
class BulletList(HasChildren[ListItem], BlockNode):
    style: BulletListStyle
    loose: bool

    @property
    def tag(self) -> str:
        return 'bullet_list'
    
@dataclass(kw_only=True)
class TaskList(HasChildren[TaskListItem], BlockNode):
    loose: bool

    @property
    def tag(self) -> str:
        return 'task_list'

@dataclass(kw_only=True)
class DefinitionList(HasChildren[DefinitionListItem], BlockNode):

    @property
    def tag(self) -> str:
        return 'definition_list'

@dataclass(kw_only=True)
class Table(HasChildren[Row], BlockNode):
    caption: Caption = field(default_factory=Caption)

    @property
    def tag(self) -> str:
        return 'table'