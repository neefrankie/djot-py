from dataclasses import dataclass
from typing import Tuple

from djot.event import (
    Event,
    BlockContainer,
)

from ..cursor import (
    Cursor,
    LineContext,
)
from ..attributes import (
    AttrFlowControl,
    AttributeParser,
    AttrParseResult,
)

from .frame import (
    ContainerCap,
    BlockFrame,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)

@dataclass
class AttributeRule(BlockRule):

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.ATTRIBUTES
    
    def try_open(self, ctx: ParsingContext) -> RuleResult:
        if not ctx.cursor.is_left_brace(ctx.line.pos):
            return RuleResult.fail()

        attr_parser = AttributeParser(ctx.cursor)

        res, end_line = self._parse_attributes(ctx.cursor, ctx.line, attr_parser)

        match res.status:
            case AttrFlowControl.CONTINUE:
                raise Exception('Unexpected continue status for attributes parsing')

            case AttrFlowControl.FAIL:
                return RuleResult.fail()
             
            case AttrFlowControl.DONE:
                if not ctx.cursor.is_blank_span(
                    res.position+1, 
                    end_line.end_offset
                ):
                    return RuleResult.fail()

                frame = BlockFrame(
                    rule=self,
                    start=ctx.line,
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
                            start=res.position,
                            end=res.position
                        )
                    )
                )

                
                return RuleResult(
                    status=FlowControl.LINE_FINISHED,
                    events=events,
                    frame=frame,
                    next_pos=end_line.to_line_end(),
                )

    def _parse_attributes(
        self, 
        cursor: Cursor, 
        ctx: LineContext, 
        parser: AttributeParser
    ) -> Tuple[AttrParseResult, LineContext]:

        res = parser.feed(ctx.pos, ctx.end_offset)

        if res.status == AttrFlowControl.CONTINUE:
            next_line = cursor.peek_line(ctx)
            if next_line is None:
                return AttrParseResult(
                    status=AttrFlowControl.FAIL,
                    position=ctx.end_offset,
                ), ctx
            return self._parse_attributes(cursor, next_line, parser)
        else:
            return res, ctx

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> RuleResult:
        # Since I don't permit newline inside attribute block,
        # we don've even have to check this.
        return RuleResult.fail()

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> RuleResult:

        return RuleResult.close()