import copy
from dataclasses import dataclass
from typing import List

from ..cursor import Cursor
from ..event import (
    BlockContainer,
    Event,
    InlineLeaf,
)
from ..common import Range

from .container import ContainerCap
from .frame import (
    BlockFrame,
    RefDefData,
    OpenStatus,
    BlockRule,
    OpenResult,
    ContinueResult,
    FrameAction,
    ParsingContext,
)

@dataclass
class ReferenceDefinitionRule(BlockRule):
    """
    A reference link definition consists of the reference label in square brackets,
    followed by a colon, followed by whitespace (or a newline)
    and the URL.

    Example:

    [ google ]: https://google.com
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.NONE
    # [anything]: 
    # re.compile(r'\[([^\]\r\n]*)\]:([ \t]+[^ \t\r\n]*)?[\r\n]')
    # [ followed by anything not ], \r or \n, followed by ], followed by :, followed by space,
    # followed by optional non-space, with newline at end.

    def try_open(self, cursor: Cursor) -> OpenResult:
        pos = cursor.pos
        token = cursor.find_ref_def(pos, cursor.line_end)
        if token is None:
            return OpenResult.not_matched()
        
        # m = cursor.find_reference_definition(pos)
        # if m is None:
        #     return OpenResult.not_matched()

        # label = m.captures[0] # anything inside []
        # value = m.captures[1].lstrip() # anything after :
        container = BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.pos, cursor.line_end),
            ref_def=RefDefData(
                key=token.label,
                indent=cursor.indent,
            ),
        )

        events = [
            Event.enter( # [
                kind=BlockContainer.REFERENCE_DEFINITION,
                span=cursor.new_span(pos, pos)
            ),
            Event.leaf( # [foo]
                kind=InlineLeaf.REFERENCE_KEY,
                # span=cursor.new_span(
                #     start=m.start,
                #     end=m.start + len(label) + 1
                # )
                span=copy.copy(token.label_span)
            )
        ]

        # if len(value) > 0:
        #     val_start = cursor.line_end - len(value)
        #     val_end = cursor.line_end - 1
        #     events.append(
        #         Event.leaf(
        #             kind=InlineLeaf.REFERENCE_VALUE,
        #             span=cursor.new_span(val_start, val_end)
        #         )
        #     )

        if token.value_span:
            events.append(
                Event.leaf(
                    kind=InlineLeaf.REFERENCE_VALUE,
                    span=copy.copy(token.value_span)
                )
            )
        
        next_pos = cursor.line_end 
        cursor.advance_pos(next_pos) # move to EOL
        
        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=container,
            events=events,
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        if frame.ref_def is None:
            return ContinueResult(
                frame_action=FrameAction.IMPLICIT_CLOSE,
            )

        if frame.ref_def.indent >= ctx.cursor.indent: # previous line was indented more than this line
            return ContinueResult(
                frame_action=FrameAction.IMPLICIT_CLOSE,
            )

        
        # Current position should not exceed the end of the line,
        # and content should be ended with a newline.
        if ctx.cursor.is_eol_reached:
            return ContinueResult(
                frame_action=FrameAction.IMPLICIT_CLOSE,
            )

        start = ctx.cursor.pos # first non space char
        if ctx.cursor.has_space(start, ctx.cursor.line_end):
            return ContinueResult(
                frame_action=FrameAction.IMPLICIT_CLOSE,
            )
        
        event = Event.leaf(
            kind=InlineLeaf.REFERENCE_VALUE,
            span=ctx.cursor.new_span(
                start=start,
                end=ctx.cursor.line_end - 1,
            )
        )

        frame.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end
        )

        ctx.cursor.advance_pos(ctx.cursor.line_end) # \n
        
        return ContinueResult(
            frame_action=FrameAction.PRESERVE,
            events=[event],
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert frame.closing_boundary is not None
        return [Event.exit(
                kind=BlockContainer.REFERENCE_DEFINITION,
                span=ctx.cursor.new_span(
                    frame.closing_boundary.start,
                    frame.closing_boundary.end,
                )
            )
        ]
        