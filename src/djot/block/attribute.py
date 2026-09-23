from dataclasses import dataclass
import re

from ..input import InputText
from ..attributes import AttributeParser
from ..common import Range

from .container import (
    ContainerCap,
    Container,
    AttributeData,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)


@dataclass
class AttributeRule(BlockRule):
    """Block attributes
    
    A line immediately beforethe block.
    Block attributes have the same syntax as inline attributes,
    but if they don't fit on one line, subsequence lines must be indented.
    Repeated attribute specifiers can be used, and the attributes
    will accumulate.

    
    {#water}
    {.important .large}
    Don't forget to turn off the water.

    In my opinion, there is a repetition of this specification.
    Repeated attribute specifiers play the same role as multiple indented lines,
    which is harder to implement.
    If we really want to support continuation to another line, why not use
    another `{ }` on a new line? Multiple lines of `{ }` is much easier to parse.

    Or more strictly, just allow block attribute on one line, and only one line of attribute
    above a block.
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.ATTRIBUTES

    _PATT_ENDLINE = re.compile(r'[ \t]*\r?\n')

    def try_open(self, cursor: InputText) -> RuleResult:        
        if not cursor.peek_char_is('{'):
            return RuleResult.fail()

        attribute_parser = AttributeParser(cursor)
        # From { to EOL
        res = attribute_parser.feed(cursor.pos, cursor.eol_start)
        if res.is_fail(): # Cursor is not moved. No need to rewind.
            return RuleResult.fail()

        if res.is_done():
            # After attributes are parsed, the line should only be left
            # with optional spaces followed by newline.
            if cursor.find_endline(res.position + 1) is None:
                # Why finished_line is not set here?
                return RuleResult.fail()

        container = Container(
            rule=self,
            data=AttributeData(
                status=res.status,
                indent=cursor.indent,
                startpos=cursor.pos,
                spans=[
                    Range(
                        start=cursor.pos,
                        end=cursor.eol_start,
                    ) # the range of attributes parsed.
                ]
            ),
            attribute_parser=attribute_parser, # so that parsing could continue to next line.
        )
        
        cursor.advance_to_eol()
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
        ) # No event is returned. They are kept in AttributeParser for easy rewind. Why finished_line is not turned to True here?

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
