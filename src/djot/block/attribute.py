from dataclasses import dataclass

from ..input import InputText
from ..attributes import AttributeParser

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
        res = attribute_parser.feed(cursor.pos, cursor.eol_start)
        if res.is_fail(): # Cursor is not moved. No need to rewind.
            return RuleResult.fail()

        # Attributes should stand alone on a line.
        if res.is_done() and not cursor.is_rest_of_line_blank(res.position + 1):
            return RuleResult.fail()

        container = Container(
            rule=self,
            data=None,
        )
        
        cursor.advance_to_eol()
        return RuleResult(
            status=FlowControl.OPEN,
            events=attribute_parser.events,
            container=container,
        ) # TODO: Why finished_line is not turned to True here?

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
