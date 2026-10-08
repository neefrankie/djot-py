from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Type, TypeVar, Union, cast

from ..event import (
    EventKind
)
from ..ast.base import (
    Attributes,
    merge_attributes,
    AstNode,
    InlineNode,
    BlockNode,
    HasText,
    HasChildren,
)
from ..ast.inline import (
    SoftBreak,
    HardBreak,
    FootnoteReference,
)
from ..ast.list import (
    DefinitionListItem,
    TaskListItem,
    ListItem,
)

from ..common import unescape_djot

from .normalize import (
    replace_newline,
)


N = TypeVar("N", bound=AstNode)

def _iter_string_content(node: AstNode) -> Iterator[str]:
    if isinstance(node, FootnoteReference):
        return
    
    if isinstance(node, HasText):
        yield node.text
    elif isinstance(node, (SoftBreak, HardBreak)):
        yield '\n'
    elif isinstance(node, HasChildren):
        for child in node.children:
            yield from _iter_string_content(child)

@dataclass(slots=True)
class ListData:
    styles: List[str]
    blanklines: bool = False
    tight: bool = False

Payload = Union[
    ListData,
]

@dataclass(slots=True)
class Frame:
    kind: EventKind
    start_pos: int
    children: List[AstNode] = field(default_factory=list)

    attributes: Attributes = field(default_factory=dict)
    last_attr_key: Optional[str] = None

    meta: Dict[str, Any] = field(default_factory=dict)

    is_image: bool = False
    format: str | None = None
    heading_level: int | None = None

    payload: Optional[Payload] = None
    
    @property
    def last_node(self) -> Optional[AstNode]:
        if self.children:
            return self.children[-1]

        return None

    def with_list_styles(self, styles: List[str]):
        self.payload = ListData(styles=styles)
        return self
    
    def add_child(self, child: AstNode):
        self.children.append(child)

    def merge_attributes(self, other: Attributes):
        self.attributes = merge_attributes(self.attributes, other)

    def iter_string_content(self):
        for node in self.children:
            yield from _iter_string_content(node) 

    def get_string_content(self) -> str:
        return ''.join(self.iter_string_content())       

    def pop_inline_children(self) -> List[InlineNode]:
        """专门提取 Inline 节点，逻辑上断言或过滤"""
        return cast(List[InlineNode], self.children)

    def pop_block_children(self) -> List[BlockNode]:
        """专门提取 Block 节点"""
        return cast(List[BlockNode], self.children)

    def pop_def_list_items(self) -> List[DefinitionListItem]:
        return cast(List[DefinitionListItem], self.children)

    def pop_task_list_items(self) -> List[TaskListItem]:
        return cast(List[TaskListItem], self.children)

    def pop_list_item(self) -> List[ListItem]:
        return cast(List[ListItem], self.children)

    def pop_children_of_type(self, node_type: Type[N]) -> List[N]:
        """如果想做到 100% 运行期安全，可以基于类型过滤/校验"""
        return [c for c in self.children if isinstance(c, node_type)]

    def set_ref_key(self, key: str):
        self.meta['ref_key'] = key
        self.meta['ref_val'] = ''

    def set_ref_val(self, val: str):
        self.meta['ref_val'] = self.meta.get('ref_val', '') + val

    def get_ref_key(self) -> str:
        return self.meta.get('ref_key', '')

    def get_ref_val(self) -> str:
        return self.meta.get('ref_val', '')

    def set_class(self, val: str):
        if 'class' in self.attributes:
            self.attributes['class'] += ' ' + val
        else:
            self.attributes['class'] += val

    def set_id(self, val: str):
        self.attributes['id'] = val

    def get_id(self) -> str:
        return self.attributes.get('id', '')

    def has_id(self) -> bool:
        return 'id' in self.attributes

    def set_attr_key(self, key: str):
        self.last_attr_key = key
        self.attributes[key] = ''

    def set_attr_val(self, val: str):
        val = replace_newline(val)
        val = unescape_djot(val)
        if self.last_attr_key:
            self.attributes[self.last_attr_key] = self.attributes[self.last_attr_key] + val
        else:
            raise Exception('Encountered value without key') 