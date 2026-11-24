from dataclasses import dataclass

from .base import (
    HasText,
    HasChildren,
    InlineNode,
    BlockNode,
    ContentBlock,
    DefinitionBlock,
    Caption,
)


@dataclass(kw_only=True)
class Para(HasChildren[InlineNode], ContentBlock):

    @property
    def tag(self) -> str:
        return 'para'

@dataclass(kw_only=True)
class Heading(HasChildren[InlineNode], ContentBlock):
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
class Section(HasChildren[BlockNode], ContentBlock):

    @property
    def tag(self) -> str:
        return 'section'

@dataclass(kw_only=True)
class Div(HasChildren[BlockNode], ContentBlock):
    caption: Caption

    @property
    def tag(self) -> str:
        return 'div'

@dataclass(kw_only=True)
class BlockQuote(HasChildren[BlockNode], ContentBlock):

    @property
    def tag(self) -> str:
        return 'block_quote'

@dataclass(kw_only=True)
class CodeBlock(HasText, ContentBlock):
    lang: str | None

    @property
    def tag(self) -> str:
        return 'code_block'

@dataclass(kw_only=True)
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

@dataclass(kw_only=True)
class Reference(DefinitionBlock):
    """
    Handles a reference link definition
    """
    label: str
    destination: str

    @property
    def tag(self) -> str:
        return 'reference'

