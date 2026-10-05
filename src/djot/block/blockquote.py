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
        if not cursor.peek_is_blockquote_prefix():
            return RuleResult.fail()

        # Djot.js performs addContainer here.
        # So all previous containers closed at this snapshot.
        container = container=Container(
            rule=self,
            start_pos=cursor.pos,
            last_eol=cursor.eol_end,
        )

        pos = cursor.pos
        next_pos = cursor.pos + 1 # after >

        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
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
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        if ctx.cursor.peek_is_blockquote_prefix():
            container.last_eol = ctx.cursor.eol_end
            next_pos = ctx.cursor.pos + 1 # Eat starting >
            # ctx.cursor.advance() # Eat starting >
            return RuleResult(
                status=FlowControl.CONTINUE,
                next_pos=next_pos,
            )
        
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
                    span=ctx.cursor.new_span(container.last_eol, container.last_eol)
                )
            ]
        )