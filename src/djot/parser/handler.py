from abc import ABC
from typing import Optional

from djot.event import (
    Event,
    Action,
)
from djot.ast import (
    AstNode,
)
from djot.common import Pos

from .state import DocumentContext, BuildingState
from .frame import Frame

class Handler(ABC):
    def __call__(self, state: BuildingState, ctx: DocumentContext, event: Event):
        if event.action:
            self.handle_container(state, ctx, event)
        else:
            self.handle_leaf(state, ctx, event)

    def handle_container(self, state: BuildingState, ctx: DocumentContext, event: Event):
        if event.action == Action.ENTER:
            frame = self.on_enter(state, ctx, event)
            if not frame:
                return

            if not state.block_attributes.is_empty:
                # Block atttributes should be transfered immediatel upon seeing a block followed.
                state.block_attributes.transfer_to(frame.attributes)

            state.push_frame(frame)
        elif event.action == Action.EXIT:
            node = self.on_exit(state, ctx, event)
            if not node:
                return
            state.add_child_to_tip(node)

    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Optional[Frame]:
        return Frame(
            kind=event.kind,
            start_pos=event.startpos,
        )
    
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Optional[AstNode]:
        return None

    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        text = ctx.get_leaf_text(event)
        pos = ctx.calc_leaf_pos(event)

        node = self.on_leaf(state, text, pos)
        if node is None:
            return

        state.add_child_to_tip(node)

    def on_leaf(self, state: BuildingState, text: str, pos: Pos | None) -> Optional[AstNode]:
        return None


