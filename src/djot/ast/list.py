from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import NamedTuple

from .base import (
    AstNode,
    HasChildren,
    InlineNode,
    BlockNode,
)

# === List ===
class BulletListStyle(StrEnum):
    PLUS = '+'
    DASH = '-'
    STAR = '*'

class ListItem(HasChildren[BlockNode], AstNode):

    @property
    def tag(self) -> str:
        return 'list_item'

@dataclass
class BulletList(HasChildren[ListItem], BlockNode):
    tight: bool
    style: BulletListStyle

    @property
    def tag(self) -> str:
        return 'bullet_list'

class OrderedListStyle(StrEnum):
    NUMBER = '1.'
    NUM_RPAREN = '1)'
    NUM_PAREN = '(1)'
    LOWER_ALPHA = 'a.'
    LOWER_ALPHA_RPAREN = 'a)'
    LOWER_ALPHA_PAREN = '(a)'
    UPPER_ALPHA = 'A.'
    UPPER_ALPHA_RPAREN = 'A)'
    UPPER_ALPHA_PAREN = '(A)'
    LOWER_ROMAN = 'i.'
    LOWER_ROMAN_RPAREN = 'i)'
    LOWER_ROMAN_PAREN = '(i)'
    UPPER_ROMAN = 'I.'
    UPPER_ROMAN_RPAREN = 'I)'
    UPPER_ROMAN_PAREN = '(I)'

@dataclass
class OrderedList(HasChildren[ListItem], BlockNode):
    style: OrderedListStyle
    tight: bool
    start: int | None
    
    @property
    def tag(self) -> str:
        return 'ordered_list'

class CheckboxStatus(Enum):
    CHECKED = 0
    UNCHECKED = 1

@dataclass
class TaskListItem(HasChildren[BlockNode], AstNode):
    status: CheckboxStatus

    @property
    def tag(self) -> str:
        return 'task_list_item'

@dataclass
class TaskList(HasChildren[TaskListItem], BlockNode):
    tight: bool

    @property
    def tag(self) -> str:
        return 'task_list'

"""
In a definition list item, the first line or lines after the `:` marker
is parsed as inline content and taken to be the _term_ defined. Any
further blocks included in the item are assumed to be the _definition_.

```
: orange

  A citrus fruit.
```
"""

@dataclass(kw_only=True)
class Term(HasChildren[InlineNode], AstNode):

    @property
    def tag(self) -> str:
        return 'term'


@dataclass(kw_only=True)
class Definition(HasChildren[InlineNode], AstNode):

    @property
    def tag(self) -> str:
        return 'definition'


class TermDefined(NamedTuple):
    term: Term
    definition: Definition


@dataclass(kw_only=True)
class DefinitionListItem(HasChildren[TermDefined], AstNode):

    @property
    def tag(self) -> str:
        return 'definition_list_item'


@dataclass(kw_only=True)
class DefinitionList(HasChildren[DefinitionListItem], BlockNode):

    @property
    def tag(self) -> str:
        return 'definition_list'