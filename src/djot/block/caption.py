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



@dataclass
class CaptionRule(BlockRule):
    """
    Attach a caption to a table usiing ^.
    It can contain inline formatting, and can extend over multiple lines,
    providing they are indented relative to the ^
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: InputText) -> OpenResult:
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
        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=container,
            events=[event],
            next_pos=next_pos,
        )

    def on_continue(
        self,
        container: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        # Check if the line is indented.
        if ctx.cursor.peek_is_whitespace():
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        container.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end,
        )
        return ContinueResult(
            action=ContinueAction.CONTINUE,
        )

    def on_close(
        self, 
        container: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert container.closing_boundary is not None

        return [
            Event.exit(
                kind=BlockContainer.CAPTION,
                span=ctx.cursor.new_span(
                    start=container.closing_boundary.start,
                    end=container.closing_boundary.end,
                )
            )
        ]
        