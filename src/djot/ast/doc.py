from dataclasses import dataclass
from typing import Dict

from .base import AstNode, BlockNode, HasChildren
from .reference import Footnote, Reference

@dataclass(kw_only=True)
class Doc(HasChildren[BlockNode], AstNode):
    references: Dict[str, Reference]
    footnotes: Dict[str, Footnote]

    @property
    def tag(self) -> str:
        return 'doc'