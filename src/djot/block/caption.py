from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
)

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

        cursor.advance_to(m.end + 1) # move to the first char after space
        container = Container(
            rule=self,
            data=None
        )
        event = Event.enter(
            kind=BlockContainer.CAPTION,
            span=cursor.current_span(), # ^ is ignored. Start from first non-space char.
        ) 
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=[event]
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        # Check if the line is indented.
        if ctx.cursor.peek_is_whitespace():
            return RuleResult.continue_ok()

        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[Event.exit(
                kind=BlockContainer.CAPTION,
                span=ctx.cursor.new_span(
                    start=ctx.cursor.pos-1, # TODO: figure out why subtract 1
                    end=ctx.cursor.pos-1
                )
            )]
        )
        