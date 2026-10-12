from djot.ast import (
    AstNode,
    Str,
)
from djot.event import Event, AttrKind
from djot.logger import logger

from .state import BuildingState, DocumentContext
from .handler import Handler

# InlineContainer.ATTR
class InlineAttrHandler(Handler):
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        """Attach inline attributes to last node"""
        frame = state.pop_frame()
        pos = ctx.calc_pos(
            frame.start_pos,
            event.endpos
        )

        if not frame.attributes:
            return None

        last_node = state.last_node
        if not last_node:
            return None

        if last_node.attributes is None:
            last_node.attributes = {}

        if not isinstance(last_node, Str):
            frame.attributes.transfer_to(last_node.attributes)
            return None

        if not last_node.text or last_node.text[-1].isspace():
            logger.warning(f'Ignoring unattached attribute: {pos.start}')
            return None

        new_node = last_node.split_at_last_space()
        if not new_node:
            frame.attributes.transfer_to(last_node.attributes)
            return None

        if new_node.attributes is None:
            new_node.attributes = {}
        
        frame.attributes.transfer_to(new_node.attributes)

        return new_node

# BlockContainer.ATTRIBUTES
class BlockAttrHandler(Handler):
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        """
        Transfer attributes longer-lived object
        so that they could be re-transfered to next block element.
        """
        frame = state.pop_frame()

        if frame.attributes.is_empty:
            return None

        frame.attributes.transfer_to(state.block_attributes)

        return None

class AttrLeafHandler(Handler):
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        frame = state.current_frame
        text = ctx.get_leaf_text(event)

        match event.kind:
            case AttrKind.CLASS:
                frame.attributes.add_class(text)
            case AttrKind.ID:
                frame.attributes.set_id(text)
            case AttrKind.KEY:
                frame.attributes.set_key(text)
            case AttrKind.VALUE:
                frame.attributes.set_val(text)