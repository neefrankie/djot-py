from dataclasses import dataclass
from typing import List, Tuple

from djot.event import (
    Event,
    BlockContainer,
)

from ..cursor import (
    Cursor,
    LineContext,
)
from ..attributes import (
    AttrStatus,
    AttributeParser,
)

from .container import (
    ContainerCap,
)
from .frame import (
    BlockFrame,
    BlockRule,
    OpenResult,
    OpenStatus,
    ContinueResult,
    ContinueAction,
    LineAction,
)

from .context import (
    ParsingContext,
    
)

def parse_attributes(
    cursor: Cursor,
    parser: AttributeParser,
    current_line: LineContext, 
) -> Tuple[AttrStatus, LineContext]:
    initial_line = current_line
    res = parser.feed(current_line.pos, current_line.end_offset)

    while res.status == AttrStatus.CONTINUE:
        next_line = cursor.peek_line(current_line)
        if next_line is None: # no more lines
            return AttrStatus.FAIL, current_line.new_pos(res.position) # The cursor should stop at res.position of last line.

        next_line = cursor.skip_frame_space(next_line)
        # Multiple lines attributes should be indented.
        if next_line.current_column <= initial_line.current_column:
            return AttrStatus.FAIL, current_line.new_pos(res.position)
        
        # res.DONE and res.FAIL should break the loop
        res = parser.feed(current_line.pos, next_line.end_offset)
        current_line = next_line

    # Now parsing result is either DONE or FAIL.
    current_line = current_line.new_pos(res.position) # move cursor.

    return res.status, current_line

@dataclass
class AttributeRule(BlockRule):

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.ATTRIBUTES
    
    def try_open(self, ctx: ParsingContext) -> OpenResult:
        if not ctx.cursor.is_left_brace(ctx.line.pos):
            return OpenResult(
                status=OpenStatus.NOT_MATCHED,
                block_start=ctx.line,
            )

        attr_parser = AttributeParser(ctx.cursor)

        status, end_line = parse_attributes(ctx.cursor, attr_parser, ctx.line)

        match status:
            case AttrStatus.CONTINUE:
                raise Exception('Unexpected continue status for attributes parsing')

            case AttrStatus.FAIL:
                return OpenResult(
                    status=OpenStatus.FALLBACK,
                    block_start=ctx.line,
                )
             
            case AttrStatus.DONE:
                if not ctx.cursor.peek_is_blank(end_line.pos+1):
                    return OpenResult(
                        status=OpenStatus.FALLBACK,
                        block_start=ctx.line,
                    )

                events = [
                    Event.enter(
                        ctx.cursor.new_span(ctx.line.pos, ctx.line.pos), 
                        BlockContainer.ATTRIBUTES
                    )
                ]

                events.extend(attr_parser.events)

                events.append(
                    Event.exit(
                        kind=BlockContainer.ATTRIBUTES,
                        # djot.js implementation incorrectly sets the
                        # block attributes to next block starting point.
                        # It should be the end brace based on human intuition and symmetry.
                        span=ctx.cursor.new_span(
                            start=end_line.pos,
                            end=end_line.pos
                        )
                    )
                )

                
                return OpenResult(
                    status=OpenStatus.MATCH_AND_CONSUMED,
                    block_start=ctx.line,
                    block_end=end_line.to_line_end(),
                    events=events,
                    frame=None,
                )



    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        # This acutally won't execute since no opening frame
        # is created.
        return ContinueResult(
            action=ContinueAction.STOP,
            line_action=LineAction.CONSUMED,
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        return []