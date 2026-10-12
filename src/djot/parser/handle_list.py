from typing import List

from djot.ast import (
    AstNode,
    DefinitionList,
    TaskList,
    BulletList,
    BulletListStyle,
    OrderedList,
    OrderedListStyle,
    Para,
    Term,
    Definition,
    DefinitionListItem,
    TaskListItem,
    ListItem,
)
from djot.common import Pos
from djot.event import (
    Event,
    ListPayload,
    CheckboxPayload,
)
from djot.common.list_style import ListStyle

from .roman import get_list_start
from .state import (
    BuildingState,
    DocumentContext
)
from .handler import Handler
from .frame import Frame, ListData, ListItemData

# BlockContainer.LIST
class ListHandler(Handler):
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        styles: List[ListStyle] = []
        if isinstance(event.payload, ListPayload):
            styles = event.payload.styles.copy()

        frame = Frame(
            kind=event.kind,
            start_pos=event.startpos,
            list_data=ListData(
                styles=styles,
            ),
        )

        state.list_depth += 1
        return frame

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        list_frame = state.pop_frame()

        pos = ctx.calc_container_pos(list_frame, event)
        if list_frame.list_data is None:
            raise Exception('No style defined for list')

        node = self._create_list_node(list_frame, pos, list_frame.list_data)
        state.list_depth -= 1
        return node

    def _create_list_node(self, frame: Frame, pos: Pos, list_data: ListData) -> AstNode:

        first_style = list_data.styles[0]
        if not first_style:
            raise Exception('No style defined for list')

        # In djot.js, it called a function `tightenContainerEnd(node);`.
        # The author might be trying to fix indeterministic cursor problem
        # generated during the event parsing pahse.
        
        if first_style.is_definition:
            return DefinitionList(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_def_list_items()
            )

        is_loose = frame.is_loose_list()

        if first_style.is_task:
            return TaskList(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_task_list_items(),
                loose=is_loose,
            )

        if first_style.is_bullet:
            return BulletList(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_list_item(),
                loose=is_loose,
                style=BulletListStyle(first_style)
            )

        assert first_style.ordered is not None

        list_start = get_list_start(
            list_data.first_marker,
            first_style.ordered,
        )
        return OrderedList(
            attributes=frame.attributes.build(),
            pos=pos,
            children=frame.pop_list_item(),
            loose=is_loose,
            style=OrderedListStyle(str(first_style.ordered)),
            start=list_start
        )


def is_definition(styles: List[ListStyle]) -> bool:
    return len(styles)==1 and styles[0].is_definition


# BlockContainer.LIST_ITEM
class ListItemHandler(Handler):
    """
    (iv) four
     
     - sub
        
       two

    +LIST
        +LIST_ITEM
            +PARA
                STR: 'four'
            -PARA
            BLANKLINE
            +LIST
                +LIST_ITEM
                    +PARA
                        STR: 'sub'
                    -PARA
                    BLANKLINE
                    +PARA
                        STR: 'two'
                    -PARA
                -LIST_ITEM
            -LIST
        -LIST_ITEM
    -LIST
    """
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        list_frame = state.current_frame # parent list
        styles = []
        if isinstance(event.payload, ListPayload):
            styles = event.payload.styles

        list_frame.merge_list_item_styles(styles, ctx.get_leaf_text(event))

        frame = Frame(
            kind=event.kind,
            start_pos=event.startpos,
            list_item_data=ListItemData(
                is_definition=is_definition(styles),
            )
        )
        return frame

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        item_frame = state.pop_frame()
        pos = ctx.calc_container_pos(item_frame, event)

        # Defintion list does not have tight/loose state.
        if item_frame.is_definition_item:
            return self._create_definition_item(item_frame, pos)

        if item_frame.list_item_data and item_frame.list_item_data.has_blank_line:
            # After list item frame is popped,
            # current frame is list.
            state.current_frame.bubble_listitem_bankline()

        if item_frame.checkbox:
            return TaskListItem(
                checkbox=item_frame.checkbox,
                attributes=item_frame.attributes.build(),
                pos=pos,
                children=item_frame.pop_block_children(),
            )

        return ListItem(
            attributes=item_frame.attributes.build(),
            pos=pos,
            children=item_frame.pop_block_children(),
        )

    def _create_definition_item(self, frame: Frame, pos: Pos) -> DefinitionListItem:
        """
        : orange

            A citrus fruit.

        +LIST
            +LIST_ITEM
                +PARA
                    STR: 'orange'
                -PARA
                BLANKLINE
                +PARA
                    STR: 'A citrus fruit.'
                -PARA
            -LIST_ITEM
        -LIST

        DefinitionList
            DefinitionListItem
                Term + Defintion
            DefinitionListItem
                Term + Defintion
        """
        if frame.children and isinstance(frame.children[0], Para):
            term = Term(
                children=frame.children[0].children
            )
            definition = Definition(
                children=frame.pop_inline_children()[1:]
            )
            return DefinitionListItem(
                attributes=frame.attributes.build(),
                pos=pos,
                term=term,
                definition=definition
            )

        term = Term(
            children=[]
        )

        definition = Definition(
            children=frame.pop_inline_children(),
        )

        return DefinitionListItem(
            attributes=frame.attributes.build(),
            pos=pos,
            term=term,
            definition=definition,
        )



# InlineLeaf.CHECKBOX
class CheckboxHandler(Handler):
    """
    - [X]

    +LIST_ITEM
    CHECKBOX
    """
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        if isinstance(event.payload, CheckboxPayload):
            
            state.current_frame.set_checkbox(event.payload.checked)

class BlanklineHandler(Handler):
    """
    Loose List
    
    - apple

    - banana

    +LIST
        +LIST_ITEM
            +PARA
                STR
            -PARA
            BLANKLINE
        -LIST_TEM
        +LIST_ITEM
            +PARA
                STR
            -PARA
        -LIST_ITEM
    -LIST

    In such case, when blankline appears,
    top frame is a LIST.

    - apple

        - banana

        - cherry

    +LIST
        +LIST_ITEM
            +PARA
                STR
            -PARA
            BLANKLINE
            +LIST
                +LIST_ITEM
                    +PARA
                        STR
                    -PARA
                    BLANKLINE
                -LIST_ITEM
                +LIST_ITEM
                    +PARA
                        STR
                    -PARA
                -LIST_ITEM
            -LIST
        -LIST_ITEM
    -LIST
    
    """
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        # Attributes must come right before a block, so we
        # reset them on blank lines.
        state.block_attributes.reset

        top_frame = state.current_frame

        if top_frame.is_list_item:
            top_frame.set_listitem_blankline()
        elif top_frame.is_list:
            top_frame.set_list_blankline()