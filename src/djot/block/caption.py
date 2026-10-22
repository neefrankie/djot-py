from dataclasses import dataclass
from typing import List

from ..cursor import Cursor
from ..event import (
    BlockContainer,
    Event,
)
from ..common import Range

from .container import ContainerCap
from .frame import (
    BlockFrame,
    OpenStatus,
    BlockRule,
    OpenResult,
    ContinueResult,
    ContinueAction,
    ParsingContext,
)



@dataclass
class CaptionRule(BlockRule):
    """
    Attach a caption to a table usiing ^.
    It can contain inline formatting, and can extend over multiple lines,
    providing they are indented relative to the ^
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: Cursor) -> OpenResult:
        m = cursor.find_caption_start()
        if not m:
            return OpenResult.not_matched()

        container = BlockFrame(
            rule=self,
            start_pos=m.start,
            closing_boundary=Range(cursor.pos, cursor.line_end)
        )

        next_pos = m.end + 1 # the first char after space
        
        event = Event.enter(
            kind=BlockContainer.CAPTION,
            span=cursor.new_span(next_pos, next_pos), # ^ is ignored. Start from first non-space char.
        ) 

        cursor.advance_pos(next_pos)
        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=container,
            events=[event],
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        # Check if the line is indented.
        if ctx.cursor.is_whitespace(ctx.cursor.pos):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        frame.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end,
        )
        return ContinueResult(
            action=ContinueAction.CONTINUE,
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert frame.closing_boundary is not None
        assert frame.inline_parser is not None
        
        events = list(frame.inline_parser.iter_merged_events())

        events.append(
            Event.exit(
                kind=BlockContainer.CAPTION,
                span=ctx.cursor.new_span(
                    start=frame.closing_boundary.start,
                    end=frame.closing_boundary.end,
                )
            )
        )

        return events
        