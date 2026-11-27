from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Generic, List, Sequence, TypeVar

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
    children: Sequence[T] = field(default_factory=list)

@dataclass(kw_only=True)
class HasText(ABC):
    text: str

@dataclass(kw_only=True)
class InlineNode(AstNode, ABC):
    pass


# sub-categorize block nodes.
# footnote and reference are not taken into the tree.
@dataclass(kw_only=True)
class BlockNode(AstNode, ABC):
    pass


@dataclass(kw_only=True)
class Caption(HasChildren[InlineNode], AstNode):

    @property
    def tag(self) -> str:
        return 'caption'