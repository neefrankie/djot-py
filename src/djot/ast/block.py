from dataclasses import dataclass

from .base import (
    AstNode,
    HasText,
    HasChildren,
    InlineNode,
    BlockNode,
    ContentBlock,
    DefinitionBlock,
)


@dataclass
class Para(HasChildren[InlineNode], ContentBlock):

    @property
    def tag(self) -> str:
        return 'para'

@dataclass
class Heading(HasChildren[InlineNode], ContentBlock):
    level: int

    @property
    def tag(self) -> str:
        return 'heading'

@dataclass
class ThematicBreak(BlockNode):
    @property
    def tag(self) -> str:
        return 'thematic_break'

@dataclass
class Section(HasChildren[BlockNode], ContentBlock):

    @property
    def tag(self) -> str:
        return 'section'

@dataclass
class Div(HasChildren[BlockNode], ContentBlock):

    @property
    def tag(self) -> str:
        return 'div'

@dataclass
class BlockQuote(HasChildren[BlockNode], ContentBlock):

    @property
    def tag(self) -> str:
        return 'block_quote'

@dataclass
class CodeBlock(HasText, ContentBlock):
    lang: str | None

    @property
    def tag(self) -> str:
        return 'code_block'

@dataclass
class RawBlock(HasText, ContentBlock):
    format: str

    @property
    def tag(self) -> str:
        return 'raw_block'

@dataclass(kw_only=True)
class Footnote(HasChildren[BlockNode], DefinitionBlock):
    label: str

    @property
    def tag(self) -> str:
        return 'footnote'

@dataclass
class Reference(DefinitionBlock):
    """
    Handles a reference link definition
    """
    label: str
    destination: str

    @property
    def tag(self) -> str:
        return 'reference'

