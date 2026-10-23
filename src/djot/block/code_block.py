import copy
from dataclasses import dataclass
from typing import List

from djot.cursor import Cursor
from djot.event import (
    BlockContainer,
    Event,
    InlineLeaf,
)
from djot.logger import logger

from .container import ContainerCap
from .frame import (
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
class CodeBlockRule(BlockRule):
    """Parse code block

    A code block starts with a line of three or more consecutive backticks,
    optionally followed by a language speicifer, but nothing else.
    The language specifier may optionally be preceded and/or followed by whitespace.
    The code block ends with a line of backticks equal or greater in length to 
    the opening backtick fence, or the endo fo the document or dlcosing block,
    if no such line is encoutered.

    ``` python
    print('hello world')
    ```

    Raw block

    A code block with `=FORMAT` where teh langauge specification would noramlly go
    is interpreted as raw content in FORMAT.

    ``` =html
    <video>
        <source src="movie.mp4" type="video/mp4">
    </video>
    ```
    
    """
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.TEXT

    def try_open(self, cursor: Cursor) -> OpenResult:
        # Find at least three ~ or ` (capture 0), 
        # followed by optional space (capture 1), followed by
        # anything but whitespace or ` (capture 2),
        # followed by optional space, followed by newline.
        pos = cursor.pos
        token = cursor.find_code_start(pos)
        if not token:
            return OpenResult.not_matched()

        container = BlockFrame(
            rule=self,
            start_pos=pos,
            indent=cursor.indent,
            code_fence=token.borders,
            # For element with explicit closing markup,
            # we cannot record its closing boudnary here.
        )

        events: List[Event] = [
            Event.enter( # ~~~ or ```
                kind=BlockContainer.CODE_BLOCK,
                span=copy.copy(token.border_span)
            )
        ]

        if token.lang_span:
            if token.is_raw:
                events.append( # =FORMAT
                    Event.leaf(
                        kind=InlineLeaf.RAW_FORMAT,
                        span=copy.copy(token.lang_span)
                    )
                )
            else:
                events.append(
                    Event.leaf(
                        kind=InlineLeaf.CODE_LANGUAGE,
                        span=copy.copy(token.lang_span)
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
        if frame.code_fence is None:
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        # Similar to fenced div, if we didn't find ending markup,
        # yield to inner nodes.
        pos = ctx.cursor.pos
        span = ctx.cursor.find_code_end(pos, frame.code_fence)
        if span is None:
            return ContinueResult(
                action=ContinueAction.CONTINUE,
            )
        
        frame.update_closing_boundary(
            span.start, 
            span.end
        )

        ctx.cursor.advance_pos(ctx.cursor.line_end)

        # If we find ending token, it should stop at this container.
        return ContinueResult(
            action=ContinueAction.STOP,
            line_action=LineAction.CONSUMED,
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        sp = ctx.cursor.pos
        ep = ctx.cursor.pos

        if frame.closing_boundary:
            sp = frame.closing_boundary.start
            ep = frame.closing_boundary.end

        event = Event.exit(
            span=ctx.cursor.new_span(sp, ep),
            kind=BlockContainer.CODE_BLOCK,
        )

        if sp == ep:
            logger.warning(f'Unclosed code block at {ctx.cursor.pos}', )

        return [event]

        

        