from dataclasses import dataclass

from .base import (
    HasText,
    HasChildren,
    InlineNode,
    BaseBlock,
    TreeBlock,
    OrphanBlock,
    Caption,
)


@dataclass(kw_only=True)
class Para(HasChildren[InlineNode], TreeBlock):

    @property
    def tag(self) -> str:
        return 'para'

@dataclass(kw_only=True)
class Heading(HasChildren[InlineNode], TreeBlock):
    level: int

    @property
    def tag(self) -> str:
        return 'heading'

@dataclass(kw_only=True)
class ThematicBreak(BaseBlock):
    @property
    def tag(self) -> str:
        return 'thematic_break'

@dataclass(kw_only=True)
class Section(HasChildren[BaseBlock], TreeBlock):

    @property
    def tag(self) -> str:
        return 'section'

@dataclass(kw_only=True)
class Div(HasChildren[BaseBlock], TreeBlock):
    caption: Caption

    @property
    def tag(self) -> str:
        return 'div'

@dataclass(kw_only=True)
class BlockQuote(HasChildren[BaseBlock], TreeBlock):

    @property
    def tag(self) -> str:
        return 'block_quote'

@dataclass(kw_only=True)
class CodeBlock(HasText, TreeBlock):
    lang: str | None

    @property
    def tag(self) -> str:
        return 'code_block'

@dataclass(kw_only=True)
class RawBlock(HasText, TreeBlock):
    format: str

    @property
    def tag(self) -> str:
        return 'raw_block'

@dataclass(kw_only=True)
class Footnote(HasChildren[BaseBlock], OrphanBlock):
    label: str

    @property
    def tag(self) -> str:
        return 'footnote'

@dataclass(kw_only=True)
class Reference(OrphanBlock):
    """
    Handles a reference link definition
    """
    label: str
    destination: str

    @property
    def tag(self) -> str:
        return 'reference'

