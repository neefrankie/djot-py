from djot.ast import (
    ThematicBreak,
)
from djot.event import (
    Event,
    EventKind,
    BlockLeaf,
)

from .state import (
    BuildingState,
    DocumentContext,
)
from .handler import Handler

class ThematicBreakHandler(Handler):

    @property
    def event_kind(self) -> EventKind:
        return BlockLeaf.THEMATIC_BREAK

    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        node = ThematicBreak(
            attributes=state.block_attributes.build(),
            pos=ctx.calc_leaf_pos(event),
        )
        state.add_child_to_tip(node)