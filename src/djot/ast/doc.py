from dataclasses import dataclass
from typing import Dict

from .base import AstNode, BaseBlock, HasChildren
from .block import Footnote, Reference

@dataclass(kw_only=True)
class Doc(AstNode, HasChildren[BaseBlock]):
    references: Dict[str, Reference]
    footnotes: Dict[str, Footnote]

    @property
    def tag(self) -> str:
        return 'doc'