from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockLeaf,
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
class ThematicBreakRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.NONE

    def try_open(self, cursor: InputText) -> RuleResult:
        """
        A line containing thre oor more * or - characters, and nothing else
        (except spaces or tabs) is treated as a thematic break. (<hr> in HTML)
        A thematic break may e indented.

        Then they went to sleep
            
            * * * *

        When they woke up, ...
        """
        # [-*][ \t]*[-*][ \t]*[-*][-* \t]*\r?\n
        # - * * also works for this regex.
        m = cursor.find_thematic_break()
        if not m:
            return RuleResult.fail()

        container = Container(
            rule=self,
            start_pos=m.start,
            closing_boundary=Range(m.end, m.end)
        )
        event = Event.leaf(
            kind=BlockLeaf.THEMATIC_BREAK,
            span=cursor.new_span(
                start=m.start,
                end=m.end,
            )
        )

        next_pos = m.end
        
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
        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE
        )