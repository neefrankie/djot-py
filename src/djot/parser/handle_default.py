from djot.ast import (
    AstNode,
    Emph,
    Strong,
    Span,
    Mark,
    Superscript,
    Subscript,
    Delete,
    Insert,
    DoubleQuoted,
    SingleQuoted,
    Str,
    SoftBreak,
    HardBreak,
    NonBreakingSpace,
    Symb,
    FootnoteReference,
    SmartPunctuation,
    SmartPunctType,
)
from djot.event import (
    Event,
    InlineContainer,
    InlineLeaf,
)
from djot.common import Pos

from .state import (
    BuildingState,
    DocumentContext,
    Mode,
)
from .handler import Handler
from .frame import Frame
from .normalize import normalize_label

class DefaultHandler(Handler):
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)

        return create_container_node(frame, pos)

    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        node = create_leaf_node(state, ctx, event)
        if node is None:
            return

        state.add_child_to_tip(node)

def create_container_node(frame: Frame, pos: Pos) -> AstNode:
    match frame.kind:
        case InlineContainer.EMPH:
            return Emph(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.STRONG:
            return Strong(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.SPAN:
            return Span(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.MARK:
            return Mark(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.SUPERSCRIPT:
            return Superscript(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.SUBSCRIPT:
            return Subscript(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.DELETE:
            return Delete(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.INSERT:
            return Insert(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.DOUBLE_QUOTED:
            return DoubleQuoted(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case InlineContainer.SINGLE_QUOTED:
            return SingleQuoted(
                pos=pos,
                children=frame.pop_inline_children(),
            )
        case _:
            raise Exception(f'{frame.kind} is not a simple node')

def create_leaf_node(state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
    text = ctx.get_leaf_text(event)
    pos = ctx.calc_leaf_pos(event)

    match event.kind:
        case InlineLeaf.STR:
            if state.mode == Mode.NORMAL:
                return Str(
                    text=text,
                    pos=pos,
                )
            
            state.current_frame.cache_text(text)
            return None
        case InlineLeaf.SOFT_BREAK:
            # '\n'
            if state.mode == Mode.NORMAL:
                return SoftBreak(
                    pos=pos
                )
            
            state.current_frame.cache_text('\n')
            return None
        case InlineLeaf.ESCAPE:
            # In other mode, simpl drop the escape char.
            if state.mode == Mode.NORMAL:
                state.current_frame.cache_text('\\')

            return None

        case InlineLeaf.HARD_BREAK:
            # '\\n'
            if state.mode == Mode.NORMAL:
                return HardBreak(
                    pos=pos
                )
            
            state.current_frame.cache_text('\n')
            return None
        case InlineLeaf.NBSP:
            # '\ '
            if state.mode == Mode.VERBATIM:
                state.current_frame.cache_text('\\ ')
                return None
            
            return NonBreakingSpace(
                pos=pos,
            )
        case InlineLeaf.SYMBOL:
            # :symbol:
            if state.mode == Mode.NORMAL:
                alias = ctx.src[event.startpos+1:event.endpos] # between :
                return Symb(
                    pos=pos,
                    alias=alias,
                )
            
            state.current_frame.cache_text(text)
            return None
        case InlineLeaf.LEFT_SINGLE_QUOTE:
            return SmartPunctuation(
                pos=pos,
                text='\'',
                type=SmartPunctType.LEFT_SINGLE_QUOTE
            )
        case InlineLeaf.RIGHT_SINGLE_QUOTE:
            return SmartPunctuation(
                pos=pos,
                text='\'',
                type=SmartPunctType.RIGHT_SINGLE_QUOTE
            )
        case InlineLeaf.LEFT_DOUBLE_QUOTE:
            return SmartPunctuation(
                pos=pos,
                text='"',
                type=SmartPunctType.LEFT_DOUBLE_QUOTE
            )
        case InlineLeaf.RIGHT_DOUBLE_QUOTE:
            return SmartPunctuation(
                pos=pos,
                text='"',
                type=SmartPunctType.RIGHT_DOUBLE_QUOTE
            )
        case InlineLeaf.ELLIPSES:
            return SmartPunctuation(
                pos=pos,
                text='...',
                type=SmartPunctType.ELLIPSES
            )
        case InlineLeaf.EN_DASH:
            return SmartPunctuation(
                pos=pos,
                text='--',
                type=SmartPunctType.EN_DASH
            )
        case InlineLeaf.EM_DASH:
            return SmartPunctuation(
                pos=pos,
                text='---',
                type=SmartPunctType.EM_DASH
            )
        case _:
            return None