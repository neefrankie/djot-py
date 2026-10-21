from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockLeaf,
    Event,
)

from .container import (
    ContainerCap,
    BlockFrame,
    OpenStatus,
    BlockRule,
    OpenResult,
    ParsingContext,
)


@dataclass
class ThematicBreakRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.NONE

    def try_open(self, cursor: InputText) -> OpenResult:
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
            return OpenResult.fail()

        event = Event.leaf(
            kind=BlockLeaf.THEMATIC_BREAK,
            span=cursor.new_span(
                start=m.start,
                end=m.end,
            )
        )

        next_pos = m.end
        
        return OpenResult(
            status=OpenStatus.MATCH_AND_CONSUMED,
            frame=None,
            events=[event],
            next_pos=next_pos,
        )

    def on_continue(
        self,
        container: BlockFrame,
        ctx: ParsingContext
    ) -> OpenResult:
        return OpenResult.stop()

    def on_close(
        self, 
        container: BlockFrame, 
        ctx: ParsingContext,
    ) -> OpenResult:
        return OpenResult(
            status=OpenStatus.CLOSE
        )