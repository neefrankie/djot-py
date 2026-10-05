from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
)
from ..logger import logger

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
            start_pos=cursor.pos,
            last_eol=cursor.eol_end,
        )

        pos = cursor.pos
        return RuleResult(
            status=FlowControl.OPEN,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=cursor.new_span(pos, pos)
                )
            ],
            container=container,
            next_pos=pos,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        # TODO This won't handle all cases.
        # Lazy content checking is determined in main loop, resulting to inconsistency.
        if not ctx.cursor.peek_is_whitespace():
            container.last_eol = ctx.cursor.eol_end
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
        logger.debug(f'Close para at {container.last_eol}. Current cursor: {ctx.cursor.pos}')
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.PARA,
                    span=ctx.cursor.new_span(container.last_eol, container.last_eol)
                )
            ]
        )