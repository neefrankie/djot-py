from dataclasses import dataclass
from typing import List

from djot.cursor import Cursor
from djot.event import (
    BlockContainer,
    Event,
)
from djot.common import Range

from .container import ContainerCap
from .frame import (
    BlockFrame,
    OpenStatus,
    BlockRule,
    OpenResult,
    ContinueResult,
    FrameAction,
    ParsingContext,
)


@dataclass
class ParaRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: Cursor) -> OpenResult:
        frame = BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.line_end, cursor.line_end)
        )

        pos = cursor.pos
        return OpenResult(
            status=OpenStatus.MATCHED,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=cursor.new_span(pos, pos)
                )
            ],
            frame=frame,
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        # TODO This won't handle all cases.
        # Lazy content checking is determined in main loop, resulting to inconsistency.
        if ctx.cursor.is_whitespace(ctx.cursor.pos):
            return ContinueResult(
                frame_action=FrameAction.IMPLICIT_CLOSE,
            )
        
        frame.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end
        )
        return ContinueResult(
            frame_action=FrameAction.PRESERVE,
        )

        

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        # Actions performed in djot.js
        # 1. transfer inline matches
        # 2. pop container
        # 3. query last event's endpos
        # 4. emit exit para event.
        assert frame.closing_boundary is not None
        assert frame.inline_parser is not None

        events= list(frame.inline_parser.iter_merged_events())

        events.append(Event.exit(
            kind=BlockContainer.PARA,
            span=ctx.cursor.new_span(
                frame.closing_boundary.start,
                frame.closing_boundary.end,
            )
        ))

        return events