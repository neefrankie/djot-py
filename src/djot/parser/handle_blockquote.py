from djot.ast import (
    AstNode,
    BlockQuote,
)
from djot.event import Event, EventKind, BlockContainer

from .state import BuildingState, DocumentContext
from .handler import Handler


class BlockquoteHandler(Handler):
    @property
    def event_kind(self) -> EventKind:
        return BlockContainer.BLOCK_QUOTE
    
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)

        return BlockQuote(
            attributes=frame.attributes.build(),
            children=frame.pop_block_children(),
            pos=pos,
        )