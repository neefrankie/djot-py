from dataclasses import dataclass
from typing import List

from ..cursor import Cursor
from ..event import (
    BlockLeaf,
    Event,
)

from .container import ContainerCap
from .frame import (
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

    def try_open(self, cursor: Cursor) -> OpenResult:
        """
        A line containing thre oor more * or - characters, and nothing else
        (except spaces or tabs) is treated as a thematic break. (<hr> in HTML)
        A thematic break may e indented.

        Then they went to sleep
            
            * * * *

        When they woke up, ...
        """
        
        if not cursor.is_thematic_break(cursor.line_start, cursor.line_end):
            return OpenResult.not_matched()

        event = Event.leaf(
            kind=BlockLeaf.THEMATIC_BREAK,
            span=cursor.new_span(
                start=cursor.pos,
                end=cursor.line_end,
            )
        )

        cursor.advance_pos(cursor.line_end)
        
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