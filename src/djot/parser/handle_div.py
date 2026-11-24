from djot.ast import (
    AstNode,
    Div,
    Caption,
)
from djot.event import (
    Event,
    EventKind,
    BlockContainer
)

from .state import (
    BuildingState,
    DocumentContext,
)
from .handler import Handler

class DivHandler(Handler):
    @property
    def event_kind(self) -> EventKind:
        return BlockContainer.DIV
    
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)
        return Div(
            attributes=frame.attributes.build(),
            pos=pos,
            children=frame.pop_block_children(),
            caption=frame.caption or Caption(children=[])
        )