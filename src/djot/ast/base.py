from abc import ABC, abstractmethod
import copy
from dataclasses import dataclass
from typing import Dict, Generic, List, Optional, TypeVar

from ..common import Pos

type Attributes = Dict[str, str]

def merge_attributes(
    target: Optional[Attributes],
    source: Attributes
) -> Attributes:
    if not target:
        return source.copy()

    result = target.copy()

    for key, value in source.items():
        if key == 'class' and key in result:
            result[key] = f'{result[key]} {value}'
        else:
            result[key] = value

    return result

@dataclass(kw_only=True)
class AstNode(ABC):
    attributes: Attributes | None = None
    pos: Pos | None = None

    @property
    @abstractmethod
    def tag(self) -> str:
        pass

    def merge_attributes(self, other: Attributes):
        self.attributes = merge_attributes(self.attributes, other)

T = TypeVar("T")

@dataclass(kw_only=True)
class HasChildren(Generic[T], ABC):
    children: List[T]

@dataclass(kw_only=True)
class HasText(ABC):
    text: str

@dataclass(kw_only=True)
class InlineNode(AstNode):
    pass

@dataclass(kw_only=True)
class BlockNode(AstNode, ABC):
    pass

@dataclass(kw_only=True)
class ContentBlock(BlockNode, ABC):
    pass

@dataclass(kw_only=True)
class DefinitionBlock(BlockNode, ABC):
    """Metadata/definition block like Footnote, Reference"""
    pass