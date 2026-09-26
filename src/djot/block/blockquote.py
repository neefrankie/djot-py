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

@dataclass(slots=True)
class BlockquoteRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.BLOCK

    def try_open(self, cursor: InputText) -> RuleResult:
        if not cursor.find_blockquote_prefix():
            return RuleResult.fail()

        event = Event.enter(
            kind=BlockContainer.BLOCK_QUOTE,
            span=cursor.current_span()
        )
        container = Container(
            rule=self,
            data=None
        )
        cursor.advance() # after >

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
        if ctx.cursor.find_blockquote_prefix():
            ctx.cursor.advance() # Eat starting >
            return RuleResult.continue_ok()
        else:
            return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.BLOCK_QUOTE,
                    span=ctx.cursor.current_span()
                )
            ]
        )