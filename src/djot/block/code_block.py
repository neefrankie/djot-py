from dataclasses import dataclass
import re
from typing import List

from ..cursor import Cursor
from ..event import (
    BlockContainer,
    Event,
    InlineLeaf,
)
from ..logger import logger

from .container import ContainerCap
from .frame import (
    BlockFrame,
    CodeBlockData,
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
        m = cursor.find_code_fence()
        if not m:
            return OpenResult.not_matched()

        border = m.captures[0] # ~~~ or ```
        ws = m.captures[1] # whitespace after fence
        lang = m.captures[2] # anything but whitespace
        is_raw = lang.startswith('=') # =FORMAT
        close_pattern = re.compile(r'(' + border + border[0:1] + r'*)' + r'[ \t]*[\r\n]')

        container = BlockFrame(
            rule=self,
            indent=cursor.indent,
            data=CodeBlockData(
                close_pattern=close_pattern,
            ),
            start_pos=cursor.pos,
            # For element with explicit closing markup,
            # we cannot record its closing boudnary here.
        )

        events: List[Event] = [
            Event.enter( # ~~~ or ```
                kind=BlockContainer.CODE_BLOCK,
                span=cursor.new_span(
                    m.start,
                    m.start + len(border) - 1, 
                )
            )
        ]

        if len(lang) > 0:
            langstart = m.start + len(border) + len(ws)

            if is_raw:
                events.append( # =FORMAT
                    Event.leaf(
                        kind=InlineLeaf.RAW_FORMAT,
                        span=cursor.new_span(
                            langstart,
                            langstart + len(lang) -1,
                        )
                    )
                )
            else:
                events.append(
                    Event.leaf(
                        kind=InlineLeaf.CODE_LANGUAGE,
                        span=cursor.new_span(
                            langstart,
                            langstart + len(lang) - 1,
                        )
                    )
                )

        cursor.advance_pos(m.end)

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
        if not isinstance(frame.data, CodeBlockData):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        # Similar to fenced div, if we didn't find ending markup,
        # yield to inner nodes.
        m = ctx.cursor.find(frame.data.close_pattern)
        if not m:
            return ContinueResult(
                action=ContinueAction.CONTINUE,
            )

        # If we find ending token, it should stop at this container.
        frame.update_closing_boundary(m.start, m.start + len(m.captures[0]) - 1)

        ctx.cursor.advance_pos(m.end)

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

        

        