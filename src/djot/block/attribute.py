from dataclasses import dataclass

from djot.input import InputText
from djot.attributes import AttributeParser
from djot.event import (
    Event,
    BlockContainer,
)

from .container import (
    ContainerCap,
    Container,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)


@dataclass
class AttributeRule(BlockRule):
    """
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.ATTRIBUTES

    def try_open(self, cursor: InputText) -> RuleResult:      
        if not cursor.peek_char_is('{'):
            return RuleResult.fail()

        attribute_parser = AttributeParser(cursor)
        # From { to EOL
        res = attribute_parser.feed(cursor.pos, cursor.line_end)
        if res.is_fail(): # Cursor is not moved. No need to rewind.
            return RuleResult.fail()

        # Attributes should stand alone on a line.
        if res.is_done() and not cursor.is_rest_of_line_blank(res.position + 1):
            return RuleResult.fail()

        container = Container(
            rule=self,
            start_pos=cursor.pos
        )

        pos = cursor.pos
        events = [
            Event.enter(cursor.new_span(pos, pos), BlockContainer.ATTRIBUTES)
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
        
        next_pos = cursor.line_end
        return RuleResult(
            status=FlowControl.OPEN,
            events=events,
            container=container,
            next_pos=next_pos,
            finished_line=True,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        # Since I don't permit newline inside attribute block,
        # we don've even have to check this.
        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:

        return RuleResult.close()
