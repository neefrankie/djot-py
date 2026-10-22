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
    ContinueAction,
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
        m = cursor.find_reference_definition()
        if m is None:
            return OpenResult.not_matched()

        label = m.captures[0] # anything inside []
        value = m.captures[1].lstrip() # anything after :
        container = BlockFrame(
            rule=self,
            data=RefDefData(
                key=label,
                indent=cursor.indent,
            ),
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.pos, cursor.line_end),
        )

        pos = cursor.pos
        events = [
            Event.enter( # [
                kind=BlockContainer.REFERENCE_DEFINITION,
                span=cursor.new_span(pos, pos)
            ),
            Event.leaf( # [foo]
                kind=InlineLeaf.REFERENCE_KEY,
                span=cursor.new_span(
                    start=m.start,
                    end=m.start + len(label) + 1
                )
            )
        ]

        if len(value) > 0:
            val_start = cursor.line_end - len(value)
            val_end = cursor.line_end - 1
            events.append(
                Event.leaf(
                    kind=InlineLeaf.REFERENCE_VALUE,
                    span=cursor.new_span(val_start, val_end)
                )
            )
        
        next_pos = cursor.line_end - 1 
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
        if not isinstance(frame.data, RefDefData):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        if frame.data.indent >= ctx.cursor.indent: # previous line was indented more than this line
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        # Find URL split over multiple lines.
        nws = ctx.cursor.find_non_whitespace()
        
        # Current position should not exceed the end of the line,
        # and content should be ended with a newline.
        if not ctx.cursor.is_before_eol(ctx.cursor.pos):
            return ContinueResult(
                action=ContinueAction.STOP,
            )
        if not nws:
            return ContinueResult(
                action=ContinueAction.STOP,
            )
        if nws.end != ctx.cursor.line_end - 1: # non-whitespace extends to EOL.
            return ContinueResult(
                action=ContinueAction.STOP,
            )
        
        event = Event.leaf(
            kind=InlineLeaf.REFERENCE_VALUE,
            span=ctx.cursor.new_span(
                start=ctx.cursor.pos,
                end=ctx.cursor.line_end - 1,
            )
        )

        frame.update_closing_boundary(ctx.cursor.line_end, ctx.cursor.line_end)

        ctx.cursor.advance_pos(ctx.cursor.line_end) # \n
        
        return ContinueResult(
            action=ContinueAction.CONTINUE,
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
        