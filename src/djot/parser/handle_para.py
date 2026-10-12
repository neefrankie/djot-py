from djot.ast import (
    AstNode,
    Para,
)
from djot.event import Event

from .state import BuildingState, DocumentContext
from .handler import Handler

class ParaHandler(Handler):

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.current_frame
        pos = ctx.calc_container_pos(frame, event)
        return Para(
            attributes=frame.attributes.build(),
            pos=pos,
            children=frame.pop_inline_children()
        )