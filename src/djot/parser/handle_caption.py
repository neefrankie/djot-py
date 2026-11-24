from djot.ast import (
    AstNode,
    Caption,
    Table,
)
from djot.event import (
    Event,
    EventKind,
    BlockContainer,
)
from djot.logger import logger

from .state import (
    BuildingState,
    DocumentContext,
)
from .handler import Handler


class CaptionHandler(Handler):
    @property
    def event_kind(self) -> EventKind:
        return BlockContainer.CAPTION
    
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame() # caption frame.
        pos = ctx.calc_container_pos(frame, event)

        last_node = state.last_node

        caption = Caption(
            attributes=frame.attributes.build(),
            pos=pos,
            children=frame.pop_inline_children()
        )
        
        if isinstance(last_node, Table):
            last_node.caption = caption
            return None

        elif state.current_frame.is_div:
            state.current_frame.store_caption(caption)

        else:
            return caption


        