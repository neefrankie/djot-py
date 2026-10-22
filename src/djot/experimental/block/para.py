from dataclasses import dataclass
from typing import List

from djot.event import (
    BlockContainer,
    Event,
)
from djot.common import Range

from .container import (
    ContainerCap,
)
from .frame import (
    BlockFrame,
    BlockRule,
    OpenResult,
    OpenStatus,
    ContinueResult,
    ContinueAction,
)
from .context import (
    ParsingContext,
    
)


@dataclass
class ParaRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, ctx: ParsingContext) -> OpenResult:
        frame = BlockFrame(
            rule=self,
            start=ctx.line,
            closing_boundary=Range(
                ctx.line.end_offset,
                ctx.line.end_offset,
            )
        )

        pos = ctx.line.pos
        return OpenResult(
            status=OpenStatus.MATCHED,
            block_start=ctx.line,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=ctx.cursor.new_span(pos, pos)
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
        if ctx.cursor.is_whitespace(ctx.line.pos):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        frame.update_closing_boundary(
            ctx.line.end_offset,
            ctx.line.end_offset,
        )
        return ContinueResult(
            action=ContinueAction.CONTINUE,
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