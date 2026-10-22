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

@dataclass(slots=True)
class BlockquoteRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.BLOCK

    def try_open(self, cursor: InputText) -> OpenResult:
        if not cursor.is_blockquote(cursor.pos):
            return OpenResult.not_matched()

        # Djot.js performs addContainer here.
        # So all previous containers closed at this snapshot.
        container = container=BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.line_end, cursor.line_end)
        )

        pos = cursor.pos

        cursor.advance_pos(cursor.pos + 1) # after >

        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=container,
            events=[
                Event.enter(
                    kind=BlockContainer.BLOCK_QUOTE,
                    span=cursor.new_span(pos, pos)
                )
            ],
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        if not ctx.cursor.is_blockquote(ctx.cursor.pos):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        frame.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end
        )
        next_pos = ctx.cursor.pos + 1 # Eat starting >
        ctx.cursor.advance_pos(next_pos)
        return ContinueResult(
            action=ContinueAction.CONTINUE,
        )
        
        

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert frame.closing_boundary is not None
        return [
            Event.exit(
                kind=BlockContainer.BLOCK_QUOTE,
                span=ctx.cursor.new_span(
                    frame.closing_boundary.start,
                    frame.closing_boundary.end,
                )
            )
        ]