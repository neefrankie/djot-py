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
            closing_boundary=Range(cursor.line_end, cursor.line_end)
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
            container.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end
            )
            next_pos = ctx.cursor.pos + 1 # Eat starting >
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
        assert container.closing_boundary is not None
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.BLOCK_QUOTE,
                    span=ctx.cursor.new_span(
                        container.closing_boundary.start,
                        container.closing_boundary.end,
                    )
                )
            ]
        )