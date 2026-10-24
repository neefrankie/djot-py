from dataclasses import dataclass
from typing import List

from ..cursor import Cursor
from ..event import (
    BlockContainer,
    Event,
)
from ..common import Range

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

    def try_open(self, cursor: Cursor) -> OpenResult:
        level = cursor.count_char('#')
        if level == 0:
            return OpenResult.not_matched()

        if not cursor.is_whitespace(cursor.pos + level):
            return OpenResult.not_matched()

        start = cursor.pos
        endchar = start + level - 1

        cursor.advance_pos(endchar + 1) # after ending #
        
        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=BlockFrame(
                rule=self,
                heading_level=level,
                start_pos=cursor.pos,
                closing_boundary=Range(cursor.line_end, cursor.line_end)
            ),
            events=[
                Event.enter(
                    kind=BlockContainer.HEADING,
                    span=cursor.new_span(start, endchar),
                )
            ],
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        level = ctx.cursor.count_char('#')
        if level == 0:
            return ContinueResult(
                action=ContinueAction.STOP,
            )
        
        if frame.heading_level is None:
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        # TODO: this seems unreasonable since the specification says 
        # you can split heading over multiple lines. 
        # The following lines do not need to have starting #.
        # In my opinion, the multi-line heading should not be allowed in the first place.
        if frame.heading_level != level: 
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        if not ctx.cursor.is_whitespace(ctx.cursor.pos + level):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        frame.update_closing_boundary(ctx.cursor.line_end, ctx.cursor.line_end)
        next_pos = ctx.cursor.pos + level # eat the leading #s

        ctx.cursor.advance_pos(next_pos)

        return ContinueResult(
            action=ContinueAction.CONTINUE,
        )
    

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert frame.closing_boundary is not None
        assert frame.inline_parser is not None

        events = list(frame.inline_parser.iter_merged_events())

        events.append(
            Event.exit(
                span=ctx.cursor.new_span(
                    frame.closing_boundary.start,
                    frame.closing_boundary.end,
                ),
                kind=BlockContainer.HEADING
            )
        )

        return events