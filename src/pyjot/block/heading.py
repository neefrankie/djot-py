from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
)

from .container import (
    ContainerCap,
    Container,
    HeadingData,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)


@dataclass
class HeadingRule(BlockRule):
    """Heading

    A heading starts with a sequence of one or more `#` characters,
    followed by whitespace. The number of characters defines the
    heading level.

    The heading text may spill over onto following lines,
    which may also be preceded by the same number of `#` characters.
    (but these can also be left off).

    The heading ends when a blank line is encountered.

    ```djot
    # A Heading that
    # takes up
    # three lines

    A paragraph, finally

    # A heading that
    takes up
    three lines

    A paragraph, finally.
    ```
    
    Here's how a heading is parsed:
    1. Apply each rule's try_open method on the # element, and this one works;
    2. try_open pushes a container on stack;
    3. cursor eat the hash symbol and stops at first space;
    4. Skip spaces;
    5. In next round, no rule applies
    6. Since HeadingRule.accepts_content is INLINE, so use InlineParser to parse the rest.
    7. When it comes to the next line, grab the container from stack;
    8. try_continue finds the smame pattern of hash symbols;
    """
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: InputText) -> RuleResult:
        m = cursor.find_bangs()
        if not m:
            return RuleResult.fail()

        # Here we need two points to determine heading starts:
        # 1. The consecutive chars and their number;
        # 2. Whitepsace following #'s.
        if not cursor.find_whitespace(m.end+1):
            return RuleResult.fail()

        level = m.end - m.start + 1 # m.end point to ending #, so length has to plus 1.

        event = Event.enter(
            kind=BlockContainer.HEADING,
            span=cursor.new_span(m.start, m.end),
        )
        container = Container(
            rule=self,
            data=HeadingData(level=level)
        )
        cursor.advance(m.end + 1) # move to after ending #
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=[event]
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        m = ctx.cursor.find_bangs()
        if not m:
            return RuleResult.fail()
        if not isinstance(container.data, HeadingData):
            return RuleResult.fail()

        # TODO: this seems unreasonable since the specification says 
        # you can split heading over multiple lines. 
        # The following lines do not need to have starting #.
        # In my opinion, the multi-line heading should not be allowed in the first place.
        if container.data.level != (m.end - m.start + 1): 
            return RuleResult.fail()

        if not ctx.cursor.find_whitespace(m.end + 1):
            return RuleResult.fail()

        ctx.cursor.advance_to(m.end + 1) # eat the leading #s

        return RuleResult.continue_ok()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        
        ep = ctx.last_span_end + 1 if ctx.last_span_end else ctx.cursor.pos
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    span=ctx.cursor.new_span(ep, ep),
                    kind=BlockContainer.HEADING
                )
            ]
        )