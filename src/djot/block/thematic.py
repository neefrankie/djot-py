from dataclasses import dataclass
from typing import List

from ..input import InputText
from ..event import (
    BlockLeaf,
    Event,
)

from .frame import (
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
            return OpenResult.not_matched()

        event = Event.leaf(
            kind=BlockLeaf.THEMATIC_BREAK,
            span=cursor.new_span(
                start=m.start,
                end=m.end,
            )
        )

        cursor.advance_pos(m.end)
        
        return OpenResult(
            status=OpenStatus.MATCH_AND_CONSUMED,
            frame=None,
            events=[event],
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        return ContinueResult(
            action=ContinueAction.STOP,
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        return []