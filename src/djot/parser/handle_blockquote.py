from djot.ast import (
    AstNode,
    BlockQuote,
)
from djot.event import Event

from .state import BuildingState, DocumentContext
from .handler import Handler


class BlockquoteHandler(Handler):
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)

        return BlockQuote(
            attributes=frame.attributes.build(),
            children=frame.pop_block_children(),
            pos=pos,
        )