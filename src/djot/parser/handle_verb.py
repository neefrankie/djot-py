from djot.ast import (
    AstNode,
    Verbatim,
    InlineMath,
    RawInline,
    CodeBlock,
    RawBlock,
)
from djot.event import (
    Event,
    EventKind,
    VerbatimKind,
    InlineLeaf,
    BlockContainer,
)
from djot.parser.frame import Frame

from .normalize import trim_verbatim, normalize_raw_format
from .state import BuildingState, DocumentContext, Mode
from .handler import Handler

# VerbatimKind.VERBATIM
class VerbatimHandler(Handler):
    """
    ``` hello ``there ```

    +VERBATIM
        STR
    -VERBATIM
    """
    @property
    def event_kind(self) -> EventKind:
        return VerbatimKind.VERBATIM
    
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        state.switch_to_verb()
        return super().on_enter(state, ctx, event)

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_pos(
            frame.start_pos,
            event.endpos
        )
        text = frame.accumulated_text
        state.switch_to_normal()

        return Verbatim(
            attributes=frame.attributes.build(),
            pos=pos,
            text=text,
        )

# VerbatimKind.DISPLAY_MATH
class DisplayMathHandler(Handler):
    """
    $$`x + y`
    """
    @property
    def event_kind(self) -> EventKind:
        return VerbatimKind.DISPLAY_MATH
    
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        state.switch_to_verb()
        return super().on_enter(state, ctx, event)

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)
        text = frame.accumulated_text
        state.switch_to_normal()

        return Verbatim(
            attributes=frame.attributes.build(),
            pos=pos,
            text=text,
        )

# VerbatimKind.INLINE_MATH
class InlineMathHandler(Handler):
    """
    $`x`
    """
    @property
    def event_kind(self) -> EventKind:
        return VerbatimKind.INLINE_MATH
    
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        state.switch_to_verb()
        return super().on_enter(state, ctx, event)

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)
        text = frame.accumulated_text

        state.switch_to_normal()

        return InlineMath(
            attributes=frame.attributes.build(),
            pos=pos,
            text=trim_verbatim(text),
        )

# InlineLeaf.RAW_FORMAT
class RawFormatHandler(Handler):
    @property
    def event_kind(self) -> EventKind:
        return InlineLeaf.RAW_FORMAT
    
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        """
        Code block:

        ``` =html
        <video>
            <source src="movie.mp4" type="video/mp4">
        </video>
        ```

        `<sometag>foos</sometag>`{=html}
        """
        text = ctx.get_leaf_text(event)
        format = normalize_raw_format(text)
        if state.mode == Mode.VERBATIM: # in a code block
            # Entered into code block.
            state.current_frame.format = format
        else: # inline raw format
            # The node is already created by this point.
            last_node = state.last_node
            if isinstance(last_node, Verbatim):
                raw_inline = RawInline(
                    attributes=last_node.attributes,
                    pos=last_node.pos,
                    format=format,
                    text=last_node.text,
                )
                state.replace_last_node(raw_inline)
            else:
                raise Exception('raw_format is not after verbatim or code_block')

# BlockContainer.CODE_BLOCK
class CodeBlockHandler(Handler):
    """
    ```ruby
    x = 5 * 6
    ```
    """
    @property
    def event_kind(self) -> EventKind:
        return BlockContainer.CODE_BLOCK
    
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        state.switch_to_verb()
        return super().on_enter(state, ctx, event)

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)

        state.switch_to_normal()

        if frame.format:
            return RawBlock(
                format=frame.format,
                attributes= frame.attributes.build(),
                pos=pos,
                text=frame.accumulated_text,
            )
        else:
            return CodeBlock(
                lang=frame.lang,
                attributes= frame.attributes.build(),
                pos=pos,
                text=frame.accumulated_text,
            )

# InlineLeaf.CODE_LANGUAGE
class CodeLangHandler(Handler):
    @property
    def event_kind(self) -> EventKind:
        return InlineLeaf.CODE_LANGUAGE
    
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        lang = ctx.get_leaf_text(event)
        state.current_frame.lang = lang