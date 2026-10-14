from djot.ast import (
    AstNode,
    Heading,
)
from djot.event import Event
from djot.parser.frame import Frame

from .state import BuildingState, DocumentContext
from .handler import Handler

class HeadingHandler(Handler):
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        return Frame(
            kind=event.kind,
            start_pos=event.startpos,
            heading_level=len(event),
        )

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)
        return Heading(
            attributes=frame.attributes.build(),
            pos=pos,
            level=frame.heading_level or 0,
            children=frame.pop_inline_children()
        )