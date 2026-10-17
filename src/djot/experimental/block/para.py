from dataclasses import dataclass

from djot.event import (
    BlockContainer,
    Event,
)
from djot.logger import logger
from djot.common import Range

from .frame import (
    ContainerCap,
    BlockFrame,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)


@dataclass
class ParaRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, ctx: ParsingContext) -> RuleResult:
        frame = BlockFrame(
            rule=self,
            start=ctx.line,
            closing_boundary=Range(
                ctx.line.end_offset,
                ctx.line.end_offset,
            )
        )

        pos = ctx.line.pos
        return RuleResult(
            status=FlowControl.OPEN,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=ctx.cursor.new_span(pos, pos)
                )
            ],
            frame=frame,
            next_pos=ctx.line,
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> RuleResult:
        # TODO This won't handle all cases.
        # Lazy content checking is determined in main loop, resulting to inconsistency.
        if not ctx.cursor.is_whitespace(ctx.line.pos):
            frame.update_closing_boundary(
                ctx.line.end_offset,
                ctx.line.end_offset,
            )
            return RuleResult.continue_ok()

        return RuleResult.fail()

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> RuleResult:
        # Actions performed in djot.js
        # 1. transfer inline matches
        # 2. pop container
        # 3. query last event's endpos
        # 4. emit exit para event.
        assert frame.closing_boundary is not None
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.PARA,
                    span=ctx.cursor.new_span(
                        frame.closing_boundary.start,
                        frame.closing_boundary.end,
                    )
                )
            ]
        )