from dataclasses import dataclass
from typing import List

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
)
from ..common import Range

from .container import (
    ContainerCap,
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
        next_pos = cursor.pos + 1 # after >

        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=container,
            events=[
                Event.enter(
                    kind=BlockContainer.BLOCK_QUOTE,
                    span=cursor.new_span(pos, pos)
                )
            ],
            next_pos=next_pos,
        )

    def on_continue(
        self,
        container: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        if ctx.cursor.peek_is_blockquote_prefix():
            container.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end
            )
            next_pos = ctx.cursor.pos + 1 # Eat starting >
            return ContinueResult(
                action=ContinueAction.CONTINUE,
                next_pos=next_pos,
            )
        
        return ContinueResult(
            action=ContinueAction.STOP,
        )

    def on_close(
        self, 
        container: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert container.closing_boundary is not None
        return [
            Event.exit(
                kind=BlockContainer.BLOCK_QUOTE,
                span=ctx.cursor.new_span(
                    container.closing_boundary.start,
                    container.closing_boundary.end,
                )
            )
        ]