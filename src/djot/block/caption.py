from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
)
from ..common import Range

from .container import (
    ContainerCap,
    Container,
    FlowControl,
    BlockRule,
    RuleResult,
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

    def try_open(self, cursor: InputText) -> RuleResult:
        m = cursor.find_caption_start()
        if not m:
            return RuleResult.fail()

        container = Container(
            rule=self,
            start_pos=m.start,
            closing_boundary=Range(cursor.pos, cursor.line_end)
        )

        next_pos = m.end + 1 # the first char after space
        
        event = Event.enter(
            kind=BlockContainer.CAPTION,
            span=cursor.new_span(next_pos, next_pos), # ^ is ignored. Start from first non-space char.
        ) 
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=[event],
            next_pos=next_pos,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        # Check if the line is indented.
        if ctx.cursor.peek_is_whitespace():
            return RuleResult.fail()

        container.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end,
        )
        return RuleResult.continue_ok()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        assert container.closing_boundary is not None

        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.CAPTION,
                    span=ctx.cursor.new_span(
                        start=container.closing_boundary.start,
                        end=container.closing_boundary.end,
                    )
                )
            ]
        )
        