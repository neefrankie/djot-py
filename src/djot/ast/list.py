from dataclasses import dataclass
from enum import Enum, StrEnum

from .base import (
    AstNode,
    HasChildren,
    InlineNode,
    BlockNode,
)


@dataclass(kw_only=True)
class ListItem(HasChildren[BlockNode], AstNode):

    @property
    def tag(self) -> str:
        return 'list_item'


class CheckboxStatus(Enum):
    CHECKED = 0
    UNCHECKED = 1

@dataclass(kw_only=True)
class TaskListItem(HasChildren[BlockNode], AstNode):
    checkbox: CheckboxStatus

    @property
    def tag(self) -> str:
        return 'task_list_item'


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
class Definition(HasChildren[BlockNode], AstNode):

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
