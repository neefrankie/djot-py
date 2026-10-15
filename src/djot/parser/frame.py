from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Type, TypeVar, cast

from djot.common import Alignment
from djot.event import (
    EventKind,
    BlockContainer,
)
from djot.ast import (
    AstNode,
    InlineNode,
    BlockNode,
    HasText,
    HasChildren,
    SoftBreak,
    HardBreak,
    FootnoteReference,
    DefinitionListItem,
    TaskListItem,
    ListItem,
    CheckboxStatus,
    Row,
    Cell,
)
from djot.logger import logger
from djot.common.list_style import ListStyle

from .attr import AttrBuilder

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
    styles: List[ListStyle]
    first_marker: str = ''
    has_internal_blank_line: bool = False
    item_has_blankline: bool = False

    def is_loose(self) -> bool:
        if self.has_internal_blank_line:
            return True

        return self.item_has_blankline

@dataclass(slots=True)
class ListItemData:
    has_blank_line: bool = False
    is_definition: bool = False

@dataclass(slots=True)
class RefDefData:
    key: str
    value: str

@dataclass(slots=True)
class Frame:
    """
    A frame is tempoary store for the full lifecycle of
    a node's events.
    """
    kind: EventKind
    start_pos: int
    children: List[AstNode] = field(default_factory=list)

    # The following are structured data extracted
    # from various events.

    # attributes has two use cases:
    # 1. processing block attributes nodes:
    # The opener '{' create a Frame first,
    # and then the following key/value events
    # are collected into this attributes.
    # When '}' shows up, this attributes is transfered
    # to parent holder temporarily, and then
    # transfered again to the next frame created for
    # a block element.
    # Attributes frame -> Temporary global store -> Node frame.
    # 
    # 2. Collect inline attributes.
    # Inline attributes is placed after a node.
    # So when inline attributes frame ends, it is 
    # transferred directly to previous node.
    attributes: AttrBuilder = field(default_factory=AttrBuilder)

    # Accumulate plain text for verbatim/reference, etc.
    text_buffer: Optional[List[str]] = None
    ref_def_data: Optional[RefDefData] = None # read on exiting reference defition; write on ref key/value
    is_image: bool = False

    list_data: Optional[ListData] = None # List
    list_item_data: Optional[ListItemData] = None

    checkbox: Optional[CheckboxStatus] = None # TaskListItem
    
    # raw foramt or code lang
    format: str | None = None
    lang: str | None = None

    heading_level: int | None = None
    row_aligns: Optional[List[Alignment]] = None
    label: str | None = None
    
    @property
    def last_child(self) -> Optional[AstNode]:
        if self.children:
            return self.children[-1]

        return None

    @property
    def accumulated_text(self) -> str:
        if self.text_buffer:
            return ''.join(self.text_buffer)
        return ''

    @property
    def is_list(self) -> bool:
        return self.kind == BlockContainer.LIST

    @property
    def is_list_item(self) -> bool:
        return self.kind == BlockContainer.LIST_ITEM

    @property
    def is_definition_item(self) -> bool:
        if not self.is_list_item:
            return False

        if self.list_item_data is None:
            return False

        return self.list_item_data.is_definition

    def cache_text(self, text: str):
        if self.text_buffer is None:
            self.text_buffer = []
        
        self.text_buffer.append(text)

    def iter_children_text(self):
            for node in self.children:
                yield from _iter_string_content(node) 
    
    def get_children_text(self) -> str:
        return ''.join(self.iter_children_text())     

    def add_child(self, child: AstNode):
        self.children.append(child)

    def replace_child(self, child: AstNode, idx: int):
        self.children[idx] = child
        

    def merge_list_item_styles(self, styles: List[ListStyle], marker: str):
        # Current frame is LIST
        if self.list_data is None:
            self.list_data = ListData(
                styles=styles,
                first_marker=marker,
            )
            return
        
        # narrow styles
        # Update list styles with latest list item style
        # If a later item has fewer styles, use it.
        # For example, if a list item starts with 'i.', it might be
        # roman numeral or alpha letter.
        # However, if later items starts with 'j.', we know its alpha.
        if styles and len(styles) < len(self.list_data.styles):
            self.list_data.styles = styles

        if not self.list_data.first_marker:
            self.list_data.first_marker = marker

        return self

    def set_list_blankline(self):
        if self.list_data:
            self.list_data.has_internal_blank_line = True
        else:
            logger.warning(f'List frame does not set list_data yet.')

    def set_listitem_blankline(self):
        """When a blankline is seen inside list item"""
        if self.list_item_data:
            self.list_item_data.has_blank_line = True
            return
        
        self.list_item_data = ListItemData(
            has_blank_line=True
        )

    def bubble_listitem_bankline(self):
        if not self.is_list:
            logger.warning(f'Cannot buble list item blanline: current frame is {self.kind}')
            return
        if self.list_data is None:
            logger.warning(f'Cannot bubble list item blanline: current does not have list_data')
            return

        self.list_data.item_has_blankline = True

    def is_loose_list(self) -> bool:
        if not self.is_list:
            raise Exception(f'Current frame is not list: {self.kind}')
        
        if self.list_data is None:
            raise Exception(f'list_data is not defined')

        if self.list_data.is_loose():
            return True

        # Inspect each list item
        for item in self.children:
            if not isinstance(item, HasChildren):
                continue
            block_children: List[AstNode] = [c for c in item.children if not isinstance(c, List)]

            if len(block_children) > 1:
                return True

        return False

    def set_checkbox(self, checked: bool):
        if not self.is_list_item:
            logger.warning(f'Checkbox status could only be set on a list item frame: current is {self.kind}')
            return

        self.checkbox = CheckboxStatus.CHECKED if checked else CheckboxStatus.UNCHECKED

    def merge_row_aligns(self, aligns: List[Alignment]):
        """Merge spearator alignment when a separator row is finished."""
        self.row_aligns = aligns
        last_child = self.last_child
        if not last_child:
            return

        # No row node added yet.
        if not isinstance(last_child, Row):
            return

        # Current frame should be a table,
        # with rows as children.
        # last child is the last row processed.
        # When reaching here, it indicates there are
        # data rows before separator rows.
        # | cell | cell |
        # | ---- | ---- |
        # Rows before a separator is row is regarded as head.
        last_child.head = True

        n = len(aligns)
        # Transfer alignment to each cell.
        for i, cell in enumerate(last_child.children):
            align = aligns[i] if i < n else Alignment.DEFAULT
            cell.head = True
            cell.align = align

    def propagate_aligns_to(self, cells: List[Cell]):
        """Porpagate alignment to the cells when building a row node."""
        if self.row_aligns is None:
            n = 0
        else:
            n = len(self.row_aligns)

        for i, cell in enumerate(cells):
            cell.align = self.row_aligns[i] if self.row_aligns and i < n else Alignment.DEFAULT

        return cells

    def push_row_align(self, align: Alignment):
        if self.row_aligns is None:
            self.row_aligns = []

        self.row_aligns.append(align)


    def set_ref_key(self, key: str):
        self.ref_def_data = RefDefData(
            key=key,
            value='',
        )

    def set_ref_val(self, val: str):
        if self.ref_def_data is None:
            # TODO: warn?
            return

        self.ref_def_data.value += val
      

    def pop_inline_children(self) -> List[InlineNode]:
        """专门提取 Inline 节点，逻辑上断言或过滤"""
        return cast(List[InlineNode], self.children)

    def pop_block_children(self, start: int | None = None, stop: int | None = None) -> List[BlockNode]:
        """专门提取 Block 节点"""
        return cast(List[BlockNode], self.children[slice(start, stop)])

    def pop_def_list_items(self) -> List[DefinitionListItem]:
        return cast(List[DefinitionListItem], self.children)

    def pop_task_list_items(self) -> List[TaskListItem]:
        return cast(List[TaskListItem], self.children)

    def pop_list_item(self) -> List[ListItem]:
        return cast(List[ListItem], self.children)

    def pop_cell_children(self) -> List[Cell]:
        return cast(List[Cell], self.children)

    def pop_children_of_type(self, node_type: Type[N]) -> List[N]:
        return [c for c in self.children if isinstance(c, node_type)]


