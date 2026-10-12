from typing import List, cast

from djot.ast import (
    AstNode,
    Caption,
    Table,
    Row,
    Cell,
)
from djot.event import (
    Event,
    TablePayload,
    BlockContainer,
)
from djot.common import Alignment
from djot.logger import logger

from .state import (
    BuildingState,
    DocumentContext,
)
from .handler import Handler
from .frame import Frame

# BlockContainer.TABLE
class TableHandler(Handler):
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        return Frame(
            kind=event.kind,
            start_pos=event.startpos,
            row_aligns=[],
        )

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)

        rows = frame.children
        caption = Caption(
            children=[]
        )

        if rows[0].tag == 'caption':
            caption = cast(Caption, rows[0])
            rows = rows[1:]

        return Table(
            attributes=frame.attributes.build(),
            pos=pos,
            caption=caption,
            children=cast(List[Row], rows)
        )

# BlockContainer.TABLE_ROW
class TableRowHandler(Handler):
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        return Frame(
            kind=event.kind, # ROW
            start_pos=event.startpos,
            row_aligns=[],
        )

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame() # a row frame.
        pos = ctx.calc_container_pos(frame, event)

        if len(frame.children) == 0: # A separator line
            # When a separator frame is finished,
            # transfer the alignemnt information to the parent frame.
            state.current_frame.merge_row_aligns(frame.row_aligns or [])
            return None
        
        frame.row_aligns = []
        cells = state.current_frame.propagate_aligns_to(frame.pop_cell_children())

        return Row(
            attributes=frame.attributes.build(),
            pos=pos,
            children=cells,
            head=False,
        )
                
# InlineLeaf.TABLE_SEPARATOR
class TableSeparatorHandler(Handler):
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        """Save separator alignment to row frame.
        
        The events looks like:

        TABLE_ROW
        TABLE_SEPARATOR
        ...
        TABLE_SEPARATOR
        TABLE_ROW

        It first create a row frame on stack.
        Then upon each separator event, the alignment
        is push to the top frame.
        When the row is ready to exit, the alignments
        are transfered to parent frame, which should be a table.
        """
        if not isinstance(event.payload, TablePayload):
            raise ValueError('TableSeparatorHandler: payload is not TablePayload')

        state.current_frame.push_row_align(event.payload.alignment)

# BlockContainer.TABLE_CELL
class TableCellHandler(Handler):
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame() # row frame
        pos = ctx.calc_container_pos(frame, event)

        return Cell(
            attributes=frame.attributes.build(),
            pos=pos,
            children=frame.pop_inline_children(),
            head=False,
            align=Alignment.DEFAULT
        )

# BlockContainer.CAPTION
class CaptionHandler(Handler):
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)

        last_node = state.last_node
        if isinstance(last_node, Table):
            caption = Caption(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_inline_children()
            )
            last_node.caption = caption
            return None

        if state.current_frame.kind == BlockContainer.DIV:
            return Caption(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_inline_children()
            )

        logger.warning(f'{pos}. Caption should follow a table or be wrapped in a div')

        
        