from dataclasses import dataclass
from typing import List

from ..input import InputText
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
class ParaRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: InputText) -> OpenResult:
        container = BlockFrame(
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
            frame=container,
            next_pos=pos,
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
                action=ContinueAction.STOP,
            )
        
        frame.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end
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
        return [
            Event.exit(
                kind=BlockContainer.PARA,
                span=ctx.cursor.new_span(
                    frame.closing_boundary.start,
                    frame.closing_boundary.end,
                )
            )
        ]