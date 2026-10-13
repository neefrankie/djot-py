from djot.ast import (
    AstNode,
    Str,
)
from djot.event import Event, AttrKind
from djot.logger import logger
from djot.common import (
    Pos,
    SourceLoc,
)

from .state import BuildingState, DocumentContext
from .handler import Handler

def find_last_whitespace(s: str):
    last_space_idx = -1

    for i in range(len(s)-1, -1, -1):
        if s[i].isspace():
            last_space_idx = i
            break

    return last_space_idx

def split_at_last_space(node: Str) -> Str | None:
    # hello world
    #      ^
    last_space_idx = find_last_whitespace(node.text)
    if last_space_idx < 0:
        return

    left_text = node.text[:last_space_idx+1]
    word_text = node.text[last_space_idx+1:]

    node.text = left_text
    word_pos: Pos | None = None
    if node.pos:
        original_end = node.pos.end
        node.pos.end = SourceLoc(
            line=original_end.line,
            col=node.pos.start.col + last_space_idx,
            offset=node.pos.start.offset + last_space_idx,
        )
        word_pos = Pos(
            start=SourceLoc(
                line=original_end.line,
                col=original_end.col - last_space_idx + 1,
                offset=original_end.offset - last_space_idx + 1,
            ),
            end=original_end,
        )

    return Str(
        text=word_text,
        pos=word_pos
    )

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
            logger.warning(f'Ignoring unattached attribute: {pos}')
            return None

        new_node = split_at_last_space(last_node)
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