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
class ParaRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: InputText) -> RuleResult:
        container = Container(
            rule=self,
            data=None,
        )

        return RuleResult(
            status=FlowControl.OPEN,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=cursor.current_span()
                )
            ],
            container=container,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        if ctx.cursor.find_whitespace() is None:
            return RuleResult.continue_ok()

        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        # Actions performed in djot.js
        # 1. transfer inline matches
        # 2. pop container
        # 3. query last event's endpos
        # 4. emit exit para event.
        ep = ctx.last_span_end + 1 if ctx.last_span_end else ctx.cursor.pos
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=ctx.cursor.new_span(ep, ep)
                )
            ]
        )