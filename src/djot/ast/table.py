from dataclasses import dataclass
from typing import TypeGuard

from ..common import Alignment

from .base import (
    AstNode,
    HasChildren,
    InlineNode,
    BlockNode,
)

@dataclass(kw_only=True)
class Cell(HasChildren[InlineNode], AstNode):
    head: bool
    align: Alignment

    @property
    def tag(self) -> str:
        return 'cell'


@dataclass(kw_only=True)
class Row(HasChildren[Cell], AstNode):
    head: bool

    @property
    def tag(self) -> str:
        return 'row'


@dataclass(kw_only=True)
class Caption(HasChildren[InlineNode], AstNode):

    @property
    def tag(self) -> str:
        return 'caption'


@dataclass(kw_only=True)
class Table(HasChildren[Row], BlockNode):
    caption: Caption

    @property
    def tag(self) -> str:
        return 'table'