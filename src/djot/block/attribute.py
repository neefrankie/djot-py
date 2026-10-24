from dataclasses import dataclass
from typing import List

from djot.cursor import Cursor
from djot.attributes import (
    AttributeParser,
    AttrStatus,
    AttrParseResult,
)
from djot.event import (
    Event,
    BlockContainer,
)
from djot.common import Range

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

def parse_attributes(
    cursor: Cursor,
    parser: AttributeParser,
) -> AttrParseResult:
    
    current_line = cursor.current_line

    initial_indented_column = current_line.current_column

    res = parser.feed(current_line.pos, current_line.end_offset)

    while res.status == AttrStatus.CONTINUE:
        next_line = cursor.peek_line(current_line)
        if next_line is None: # no more lines
            return AttrParseResult(
                status=AttrStatus.FAIL,
                position=res.position,
            )

        next_line = cursor.skip_space(next_line)
        # Multiple lines attributes should be indented.
        if next_line.current_column <= initial_indented_column:
            return AttrParseResult(
                status=AttrStatus.FAIL,
                position=res.position,
            )
        
        # res.DONE and res.FAIL should break the loop
        res = parser.feed(next_line.pos, next_line.end_offset)
        current_line = next_line

    return res

@dataclass
class AttributeRule(BlockRule):

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.ATTRIBUTES

    def try_open(self, cursor: Cursor) -> OpenResult:      
        if not cursor.is_left_brace(cursor.pos):
            return OpenResult(
                status=OpenStatus.NOT_MATCHED,
            )

        start = cursor.pos
        attribute_parser = AttributeParser(cursor)
        
        res = attribute_parser.feed(start, cursor.line_end)

        match res.status:
            case AttrStatus.CONTINUE:
                raise Exception('Unexpected continue status for attributes parsing')
            
            case AttrStatus.FAIL:
                return OpenResult(
                    status=OpenStatus.FALLBACK,
                    fallback_span=Range(start, res.position)
                )

            case AttrStatus.DONE:
                # Attributes should stand alone on a line.
                if not cursor.is_ahead_blank(res.position + 1):
                    return OpenResult(
                        status=OpenStatus.FALLBACK,
                        fallback_span=Range(start, res.position)
                    )

        frame = BlockFrame(
            rule=self,
            start_pos=start
        )

        events = [
            Event.enter(
                cursor.new_span(start, start),
                BlockContainer.ATTRIBUTES
            )
        ]

        events.extend(attribute_parser.events)

        events.append(
            Event.exit(
                kind=BlockContainer.ATTRIBUTES,
                # NOTE: djot.js implementation incorrectly sets the
                # block attributes to next block starting point.
                # It should be the end brace based on human intuition and symmetry.
                span=cursor.new_span(
                    start=res.position,
                    end=res.position
                )
            )
        )
        
        cursor.advance_pos(cursor.line_end)
        return OpenResult(
            status=OpenStatus.MATCH_AND_CONSUMED,
            events=events,
            frame=frame,
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        """
        There's a potential problem in a special case:

        {.bar}
        {#foo}

        In the first line, you created a frame and pushed it on stack.
        Then in continue method, you set action to CLOSE and line_action to CONSUMED.
        When it comes to the second line, it will try this frame's continue mmethod.
        It find out it should close so it stops and pop all frame from this one.
        And then it find out line_action is consumed, so it will jump directly to the next line.
        No open is even tried for the second line.

        The solution is never creating a frame if you are sure you have finished a block in open stage.
        """
        return ContinueResult(
            action=ContinueAction.STOP,
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        return []
