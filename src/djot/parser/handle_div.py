from djot.ast import (
    AstNode,
    Div,
)
from djot.event import (
    Event,
)

from .state import (
    BuildingState,
    DocumentContext,
)
from .handler import Handler

class DivHandler(Handler):
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)
        return Div(
            attributes=frame.attributes.build(),
            pos=pos,
            children=frame.pop_block_children(),
        )