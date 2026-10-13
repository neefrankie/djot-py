from dataclasses import dataclass
from typing import Dict, List

from .base import AstNode, BlockNode, HasChildren
from .block import Footnote, Reference

@dataclass(kw_only=True)
class Doc(AstNode, HasChildren[BlockNode]):
    references: Dict[str, Reference]
    footnotes: Dict[str, Footnote]

    @property
    def tag(self) -> str:
        return 'doc'