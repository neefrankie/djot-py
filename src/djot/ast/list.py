from dataclasses import dataclass
from enum import Enum, StrEnum

from .base import (
    AstNode,
    HasChildren,
    InlineNode,
    BaseBlock,
)

# === List ===
class BulletListStyle(StrEnum):
    PLUS = '+'
    DASH = '-'
    STAR = '*'


@dataclass(kw_only=True)
class ListItem(HasChildren[BaseBlock], AstNode):

    @property
    def tag(self) -> str:
        return 'list_item'

@dataclass(kw_only=True)
class BulletList(HasChildren[ListItem], BaseBlock):
    style: BulletListStyle
    loose: bool

    @property
    def tag(self) -> str:
        return 'bullet_list'

# TODO: it could be classified into:
# - Alpha/Number/Roman
# - Dot/Paren/TwoParen
# - UpperCase/LowerCase for Alpha/Roman
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

@dataclass(kw_only=True)
class OrderedList(HasChildren[ListItem], BaseBlock):
    style: OrderedListStyle
    start: int | None
    loose: bool
    
    @property
    def tag(self) -> str:
        return 'ordered_list'

class CheckboxStatus(Enum):
    CHECKED = 0
    UNCHECKED = 1

@dataclass(kw_only=True)
class TaskListItem(HasChildren[BaseBlock], AstNode):
    checkbox: CheckboxStatus

    @property
    def tag(self) -> str:
        return 'task_list_item'

@dataclass(kw_only=True)
class TaskList(HasChildren[TaskListItem], BaseBlock):
    loose: bool

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
class Definition(HasChildren[BaseBlock], AstNode):

    @property
    def tag(self) -> str:
        return 'definition'

@dataclass(kw_only=True)
class DefinitionListItem(AstNode):
    term: Term
    definition: Definition

    @property
    def tag(self) -> str:
        return 'definition_list_item'

@dataclass(kw_only=True)
class DefinitionList(HasChildren[DefinitionListItem], BaseBlock):

    @property
    def tag(self) -> str:
        return 'definition_list'