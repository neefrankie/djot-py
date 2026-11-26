from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Generic, List, TypeVar

from djot.common import Pos

type Attributes = Dict[str, str]


@dataclass(kw_only=True)
class AstNode(ABC):
    attributes: Attributes | None = None
    pos: Pos | None = None

    @property
    @abstractmethod
    def tag(self) -> str:
        pass


T = TypeVar("T")

@dataclass(kw_only=True)
class HasChildren(Generic[T], ABC):
    children: List[T] = field(default_factory=list)

@dataclass(kw_only=True)
class HasText(ABC):
    text: str

@dataclass(kw_only=True)
class InlineNode(AstNode, ABC):
    pass

@dataclass(kw_only=True)
class BaseBlock(AstNode, ABC):
    """
    All block elements should inherit from this.
    It plays the role of blockTags and isBlock in djot.js
    So use instance(node, BaseBlock) for isBlock function.
    """
    pass

# sub-categorize block nodes.
# footnote and reference are not taken into the tree.
@dataclass(kw_only=True)
class TreeBlock(BaseBlock, ABC):
    pass

@dataclass(kw_only=True)
class OrphanBlock(BaseBlock, ABC):
    """Footnote, Reference that are not part of AST"""
    pass

@dataclass(kw_only=True)
class Caption(HasChildren[InlineNode], AstNode):

    @property
    def tag(self) -> str:
        return 'caption'