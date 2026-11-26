from dataclasses import dataclass

from .base import (
    AstNode,
    HasChildren,
    BlockNode,
)

# Block elements that does not take part in AST.
@dataclass(kw_only=True)
class Footnote(HasChildren[BlockNode], AstNode):
    label: str

    @property
    def tag(self) -> str:
        return 'footnote'

@dataclass(kw_only=True)
class Reference(AstNode):
    """
    Handles a reference link definition
    """
    label: str
    destination: str

    @property
    def tag(self) -> str:
        return 'reference'