from dataclasses import dataclass
import re
from typing import List

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
    CodeBlockData,
    FlowControl,
    BlockRule,
    RuleResult,
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

    def try_open(self, cursor: InputText) -> RuleResult:
        # Find at least three ~ or ` (capture 0), 
        # followed by optional space (capture 1), followed by
        # anything but whitespace or ` (capture 2),
        # followed by optional space, followed by newline.
        m = cursor.find_code_fence()
        if not m:
            return RuleResult.fail()

        border = m.captures[0] # ~~~ or ```
        ws = m.captures[1] # whitespace after fence
        lang = m.captures[2] # anything but whitespace
        is_raw = lang.startswith('=') # =FORMAT
        close_pattern = re.compile(r'(' + border + border[0:1] + r'*)' + r'[ \t]*[\r\n]')

        container = Container(
            rule=self,
            indent=cursor.indent,
            data=CodeBlockData(
                close_pattern=close_pattern,
            )
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

        cursor.advance_to(m.end)
        return RuleResult(
            status=FlowControl.OPEN,
            events=events,
            container=container,
            finished_line=True
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        if not isinstance(container.data, CodeBlockData):
            return RuleResult.fail()

        # Similar to fenced div, if we didn't find ending markup,
        # yield to inner nodes.
        m = ctx.cursor.find(container.data.close_pattern)
        if not m:
            return RuleResult.continue_ok()

        # If we find ending token, it should stop at this container.
        container.data.span = Range(
            start=m.start,
            end=m.start + len(m.captures[0]) - 1
        )

        ctx.cursor.advance_to(m.end) # \n

        return RuleResult(
            status=FlowControl.FAIL, # TODO: change to CLOSE
            finished_line=True
        )

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        sp = ctx.cursor.pos
        ep = ctx.cursor.pos

        if isinstance(container.data, CodeBlockData):
            if container.data.span:
                sp = container.data.span.start
                ep = container.data.span.end

        event = Event.exit(
            span=ctx.cursor.new_span(sp, ep),
            kind=BlockContainer.CODE_BLOCK,
        )

        if sp == ep:
            print('Unclosed code block', ctx.cursor.pos)

        return RuleResult(
            status=FlowControl.CLOSE,
            events=[event]
        )

        

        