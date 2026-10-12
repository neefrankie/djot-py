from djot.ast import (
    AstNode,
    Footnote,
    FootnoteReference,
)
from djot.common import Pos
from djot.event import (
    Event,
)
from djot.logger import logger

from .state import (
    BuildingState,
    DocumentContext,
)
from .handler import Handler
from .normalize import normalize_label

# BlockContainer.FOOTNOTE
class FootnoteHandler(Handler):
    """
    [^note]: This is a
    note
      second par
      
    after note

    FOOTNOTE
    NOTE_LABEL: note
    FOOTNOTE
    """
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)

        if frame.label:
            label = normalize_label(frame.label)
            fn = Footnote(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_block_children(),
                label=label
            )
            state.add_footnote(fn)
        else:
            logger.warning(f'Ignoring footnote without a label. {pos.end}')

# InlineLeaf.NOTE_LABEL
class NoteLabelHandler(Handler):
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        state.current_frame.label = ctx.get_leaf_text(event) # foo in [^foo]

# InlineLeaf.FOOTNOTE_REF
class FootnoteRefHandler(Handler):
    """
    [^ref]
    """
    def on_leaf(self, state: BuildingState, text: str, pos: Pos) -> AstNode | None:
        fn_ref = text[2:-1]
        return FootnoteReference(
            pos=pos,
            text=normalize_label(fn_ref)
        )