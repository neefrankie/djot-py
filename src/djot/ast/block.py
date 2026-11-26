from dataclasses import dataclass

from .base import (
    HasText,
    HasChildren,
    InlineNode,
    BlockNode,
    Caption,
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
class BlockQuote(HasChildren[BlockNode], BlockNode):

    @property
    def tag(self) -> str:
        return 'block_quote'

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
