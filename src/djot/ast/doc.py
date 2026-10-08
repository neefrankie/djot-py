from dataclasses import dataclass
from typing import Dict, List

from .base import AstNode, BlockNode
from .block import Footnote, Reference

@dataclass(kw_only=True)
class Doc(AstNode):
    children: List[BlockNode]
    references: Dict[str, Reference]
    footnotes: Dict[str, Footnote]
    

    @property
    def tag(self) -> str:
        return 'doc'