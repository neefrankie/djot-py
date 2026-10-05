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
        level = cursor.count_char('#')
        if level == 0:
            return RuleResult.fail()

        if not cursor.is_whitespace(cursor.pos + level):
            return RuleResult.fail()

        start = cursor.pos
        endchar = start + level - 1

        next_pos = endchar + 1 # move to after ending #
        
        return RuleResult(
            status=FlowControl.OPEN,
            container=Container(
                rule=self,
                data=HeadingData(level=level),
                start_pos=cursor.pos,
                last_eol=cursor.eol_end,
            ),
            events=[
                Event.enter(
                    kind=BlockContainer.HEADING,
                    span=cursor.new_span(start, endchar),
                )
            ],
            next_pos=next_pos,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        level = ctx.cursor.count_char('#')
        if level == 0:
            return RuleResult.fail()
        
        if not isinstance(container.data, HeadingData):
            return RuleResult.fail()

        # TODO: this seems unreasonable since the specification says 
        # you can split heading over multiple lines. 
        # The following lines do not need to have starting #.
        # In my opinion, the multi-line heading should not be allowed in the first place.
        if container.data.level != level: 
            return RuleResult.fail()

        if not ctx.cursor.is_whitespace(ctx.cursor.pos + level):
            return RuleResult.fail()

        container.last_eol = ctx.cursor.eol_end
        next_pos = ctx.cursor.pos + level # eat the leading #s

        return RuleResult(
            status=FlowControl.CONTINUE,
            next_pos=next_pos,
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
                    span=ctx.cursor.new_span(container.last_eol, container.last_eol),
                    kind=BlockContainer.HEADING
                )
            ]
        )