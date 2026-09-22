from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
    InlineLeaf,
)
from ..common import Range

from .container import (
    ContainerCap,
    Container,
    RefDefData,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)

@dataclass
class ReferenceDefinitionRule(BlockRule):
    """
    A reference link definition consists of the reference label in square brackets,
    followed by a colon, followed by whitespace (or a newline)
    and the URL.

    Example:

    [ google ]: https://google.com
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.NONE
    # [anything]: 
    # re.compile(r'\[([^\]\r\n]*)\]:([ \t]+[^ \t\r\n]*)?[\r\n]')
    # [ followed by anything not ], \r or \n, followed by ], followed by :, followed by space,
    # followed by optional non-space, with newline at end.

    def try_open(self, cursor: InputText) -> RuleResult:
        m = cursor.find_reference_definition()
        if m is None:
            return RuleResult.fail()

        label = m.captures[0] # anything inside []
        value = m.captures[1].lstrip() # anything after :
        container = Container(
            rule=self,
            data=RefDefData(
                key=label,
                indent=cursor.indent,
            )
        )
        events = [
            Event.enter( # [
                kind=BlockContainer.REFERENCE_DEFINITION,
                span=cursor.current_span()
            ),
            Event.leaf( # [foo]
                kind=InlineLeaf.REFERENCE_KEY,
                span=cursor.new_span(
                    start=m.start,
                    end=m.start + len(label) + 1
                )
            )
        ]
        if len(value) > 0:
            events.append(
                Event.leaf(
                    kind=InlineLeaf.REFERENCE_VALUE,
                    span=cursor.new_span(
                        start=cursor.eol_start - len(value), # start position of value
                        end=cursor.eol_start - 1 # end position of value
                    )
                )
            )

        cursor.advance_to(cursor.eol_start - 1) # move to EOL
        # TODO: why not flag finished_line = True since the whole line is gobbled.
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=events,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        if not isinstance(container.data, RefDefData):
            return RuleResult.fail()

        if container.data.indent >= ctx.cursor.indent: # previous line was indented more than this line
            return RuleResult.fail()

        # Find URL split over multiple lines.
        nws = ctx.cursor.find_whitespace()
        if not nws:
            return RuleResult.fail()
        # Current position should not exceed the end of the line,
        # and content should be ended with a newline.
        if ctx.cursor.pos >= ctx.cursor.eol_start:
            return RuleResult.fail()
        if nws.end != ctx.cursor.eol_start - 1:
            return RuleResult.fail()
        
        event = Event.leaf(
            kind=InlineLeaf.REFERENCE_VALUE,
            span=ctx.cursor.new_span(
                start=ctx.cursor.pos,
                end=ctx.cursor.eol_start - 1,
            )
        )
        ctx.cursor.advance_to(ctx.cursor.eol_start) # \n
        return RuleResult(
            status=FlowControl.CONTINUE,
            events=[event],
        )

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.REFERENCE_DEFINITION,
                    span=Range(
                        start=ctx.cursor.pos,
                        end=ctx.cursor.pos,
                    )
                )
            ]
        )