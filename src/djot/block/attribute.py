from dataclasses import dataclass
from typing import List

from djot.input import InputText
from djot.attributes import (
    AttributeParser,
    AttrStatus
)
from djot.event import (
    Event,
    BlockContainer,
)

from .frame import (
    ContainerCap,
    BlockFrame,
    OpenStatus,
    BlockRule,
    OpenResult,
    ContinueResult,
    ContinueAction,
    LineAction,
    ParsingContext,
)


@dataclass
class AttributeRule(BlockRule):

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.ATTRIBUTES

    def try_open(self, cursor: InputText) -> OpenResult:      
        if not cursor.is_left_brace(cursor.pos):
            return OpenResult(
                status=OpenStatus.NOT_MATCHED,
            )

        attribute_parser = AttributeParser(cursor)
        
        res = attribute_parser.feed(cursor.pos, cursor.line_end)

        match res.status:
            case AttrStatus.FAIL:
                return OpenResult(
                    status=OpenStatus.FALLBACK,
                )

            case AttrStatus.DONE:
                # Attributes should stand alone on a line.
                if not cursor.is_rest_of_line_blank(res.position + 1):
                    return OpenResult(
                        status=OpenStatus.FALLBACK,
                    )

        container = BlockFrame(
            rule=self,
            start_pos=cursor.pos
        )

        pos = cursor.pos
        events = [
            Event.enter(
                cursor.new_span(pos, pos),
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
            frame=container,
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        # Since I don't permit newline inside attribute block,
        # we don've even have to check this.
        return ContinueResult(
            action=ContinueAction.CLOSE,
            line_action=LineAction.CONSUMED,
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        return []
