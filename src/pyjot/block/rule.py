from dataclasses import dataclass
import re
from typing import List, NamedTuple, Optional

from ..input import InputText
from ..inline import InlineParser
from ..attributes import AttributeParser
from ..event import (
    BlockContainer,
    BlockLeaf,
    AttrKind,
    Alignment,
    Event,
    InlineLeaf,
)
from ..common import Range
from ..options import Options

from .list import get_list_styles
from .container import (
    ContainerCap,
    Container,
    HeadingData,
    FootnoteData,
    RefDefData,
    ListData,
    FencedDivData,
    CodeBlockData,
    AttributeData,
    TableData,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)


@dataclass
class ParaRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: InputText) -> RuleResult:
        container = Container(
            rule=self,
            data=None,
        )

        return RuleResult(
            status=FlowControl.OPEN,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=cursor.current_span()
                )
            ],
            container=container,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        if ctx.cursor.find_whitespace() is None:
            return RuleResult.continue_ok()

        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        # Actions performed in djot.js
        # 1. transfer inline matches
        # 2. pop container
        # 3. query last event's endpos
        # 4. emit exit para event.
        ep = ctx.last_span_end + 1 if ctx.last_span_end else ctx.cursor.pos
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=ctx.cursor.new_span(ep, ep)
                )
            ]
        )

@dataclass
class BlockquoteRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.BLOCK

    def try_open(self, cursor: InputText) -> RuleResult:
        if not cursor.find_blockquote_prefix():
            return RuleResult.fail()

        event = Event.enter(
            kind=BlockContainer.BLOCK_QUOTE,
            span=cursor.current_span()
        )
        container = Container(
            rule=self,
            data=None
        )
        cursor.advance() # after >

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
        if ctx.cursor.find_blockquote_prefix():
            ctx.cursor.advance() # Eat starting >
            return RuleResult.continue_ok()
        else:
            return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.BLOCK_QUOTE,
                    span=ctx.cursor.current_span()
                )
            ]
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

@dataclass
class CaptionRule(BlockRule):
    """
    Attach a caption to a table usiing ^.
    It can contain inline formatting, and can extend over multiple lines,
    providing they are indented relative to the ^
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: InputText) -> RuleResult:
        m = cursor.find_caption_start()
        if not m:
            return RuleResult.fail()

        cursor.advance_to(m.end + 1) # move to the first char after space
        container = Container(
            rule=self,
            data=None
        )
        event = Event.enter(
            kind=BlockContainer.CAPTION,
            span=cursor.current_span(), # ^ is ignored. Start from first non-space char.
        ) 
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
        # Check if the line is indented.
        if ctx.cursor.find_whitespace() is None:
            return RuleResult.continue_ok()

        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[Event.exit(
                kind=BlockContainer.CAPTION,
                span=ctx.cursor.new_span(
                    start=ctx.cursor.pos-1, # TODO: figure out why subtract 1
                    end=ctx.cursor.pos-1
                )
            )]
        )
        
@dataclass
class FootnoteRule(BlockRule):
    """Footnote definition

    A footnote consists of a footnote reference followed
    by a colon followed by the contents of the note,
    indented to any column beyond column in which
    the reference starts.
    The contents of the note are parsed as block-level content.

    [^foo]: This is a note
        with two paragraphs.

        Second paragraph.

        > a block quote in the note.

    Should go before reference definitions.
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.BLOCK

    def try_open(self, cursor: InputText) -> RuleResult:
        m = cursor.find_footnotestart()
        if m is None:
            return RuleResult.fail()

        # [^foo]:SPACE
        start_pos = m.start # [
        end_pos = m.end # space aftr :
        label = m.captures[0] # foo
        container = Container(
            rule=self,
            data=FootnoteData(
                label=label,
                indent=cursor.indent,
            )
        )
        events = [
            Event.enter( # [
                kind=BlockContainer.FOOTNOTE,
                span=cursor.new_span(
                    start=start_pos,
                    end=start_pos,
                ),
            ), 
            Event.leaf( # foo
                kind=InlineLeaf.NOTE_LABEL,
                span=cursor.new_span(
                    start=start_pos+2, # skip [^
                    end=end_pos-3, # skip the last ]:\s
                )
            ) 
        ]
        cursor.advance_to(end_pos) # move to first space
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
        if not isinstance(container.data, FootnoteData):
            return RuleResult.fail()

        if ctx.cursor.indent > container.data.indent: # line start
            return RuleResult.continue_ok()

        if ctx.cursor.pos == ctx.cursor.eol_start: # line end
            return RuleResult.continue_ok()

        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[Event.exit(
                kind=BlockContainer.FOOTNOTE,
                span=ctx.cursor.current_span()
            )]
        )

@dataclass
class ReferenceDefinitionRule(BlockRule):
    """
    A reference link definition consists of the reference label in square brackets,
    followed by a colon, followdd by whitespace (or a newline)
    and the URL.

    Example:
        [google]: https://google.com
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
            Event.leaf( # google in [google]
                kind=InlineLeaf.REFERENCE_KEY,
                span=cursor.new_span(
                    start=m.start,
                    end=m.start + len(label) - 1 # TODO: check this.
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

@dataclass
class ThematicBreakRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.NONE

    def try_open(self, cursor: InputText) -> RuleResult:
        """
        A line containing thre oor more * or - characters, and nothing else
        (except spaces or tabs) is treated as a thematic break. (<hr> in HTML)
        A thematic break may e indented.

        Then they went to sleep
            
            * * * *

        When they woke up, ...
        """
        # [-*][ \t]*[-*][ \t]*[-*][-* \t]*\r?\n
        # - * * also works for this regex.
        m = cursor.find_thematic_break()
        if not m:
            return RuleResult.fail()

        container = Container(
            rule=self,
            data=None
        )
        event = Event.leaf(
            kind=BlockLeaf.THEMATIC_BREAK,
            span=cursor.new_span(
                start=m.start,
                end=m.end,
            )
        )
        cursor.advance_to(m.end)
        # TODO: why not flag finished_line here since it of course gobbled the whole line.
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=[event],
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE
        )

@dataclass
class ListRule(BlockRule):
    """
    A list is simply a sequence of list items of the same type.
    Changing ordered list style or bullet will stop one list and start a new one.
    """
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.LIST_ITEM

    def try_open(self, cursor: InputText) -> RuleResult:
        m = cursor.find_list_marker()
        if not m:
            return RuleResult.fail()
        start_pos = m.start
        end_pos = m.end # whitespace
        marker = cursor.src[start_pos:end_pos]
        # A bullete list item that begins with [ ], [X] or [x]
        # followed by a space is a task list item.
        # - [ ]SPACE
        # - [X]SPACE
        # - [x]SPACE
        mtask = cursor.find_task_list_marker()
        if mtask is not None:
            marker = cursor.src[mtask.start:mtask.start + 5] # total length 6 chars. +5 points to trailng space.

        # ['+'], ['-'], ['*'], [':']
        # ['-X']
        # ['(1)'], ['1.'], ['1)']
        # ['(i)', '(a)'], ['i.', 'a.'], ['i)', 'a)']
        # ['(I)', '(A)'], ['I.', 'A.'], ['I)', 'A)']
        # ['(i)'], ['i.'], ['i)']
        # ['(I)'], ['I.'], ['I)']
        # ['(a)'], ['a.'], ['a)']
        # ['(A)'], ['A.'], ['A)']
        styles = get_list_styles(marker)
        if len(styles) == 0:
            return RuleResult.fail()
        
        container = Container(
            rule=self,
            data=ListData(
                styles=styles,
                indent=cursor.indent
            )
        )

        event = Event.enter(
            kind=BlockContainer.LIST,
            span=cursor.new_span(
                start=start_pos,
                end=end_pos - 1, # ignore trailing space.
            ),
        ).with_list_styles(styles)

        # NOTE: cursor is not moved.
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=[event],
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        if not isinstance(container.data, ListData):
            return RuleResult.fail()

        if ctx.cursor.indent > container.data.indent:
            return RuleResult.continue_ok()

        if ctx.cursor.pos == ctx.cursor.eol_start:
            return RuleResult.continue_ok()

        m = ctx.cursor.find_list_marker()
        if m is None:
            return RuleResult.fail()

        marker = ctx.cursor.src[m.start:m.end]
        mtask = ctx.cursor.find_task_list_marker()
        if mtask is not None:
            marker = ctx.cursor.src[mtask.start:mtask.start + 5]

        styles = get_list_styles(marker)
        
        newstyles: List[str] = []
        for prev_style in container.data.styles:
            if prev_style in styles:
                newstyles.append(prev_style)

        if not newstyles:
            return RuleResult.fail()

        container.data.styles = newstyles
        return RuleResult.continue_ok()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[Event.exit(
                kind=BlockContainer.LIST,
                span=ctx.cursor.current_span()
            )]
        )

@dataclass
class ListItemRule(BlockRule):
    kind: ContainerCap = ContainerCap.LIST_ITEM
    accepts_content: ContainerCap = ContainerCap.BLOCK

    def try_open(self, cursor: InputText) -> RuleResult:
        """
        A list item consists of a list marker, followed by a space (or a newline)
        followed by one or more lines, indented relative to the list marker.
        """
        m = cursor.find_list_marker()
        if m is None:
            return RuleResult.fail()
        
        sp = m.start
        ep = m.end
        marker = cursor.src[sp:ep]
        checkbox = None

        # # perform second search from current pos
        # Why it perfroms a second search only after find_list_marker succeeded?
        # A task marker must starts with one of `*`, `+` or `-`.
        # In find_list_marker, there is a group of match for [-*+:],
        # so if find_list_marker fails, no need to try find_task_marker.
        # If find_task_marker matches, then find_list_marker must succeed.
        mtask = cursor.find_task_list_marker() 
        if mtask is not None:
            marker = cursor.src[mtask.start:mtask.end+5] # - [X]
            checkbox = cursor.src[mtask.start+3:mtask.start+4] # X

        styles = get_list_styles(marker)
        if len(styles) == 0:
            return RuleResult.fail()

        container = Container(
            rule=self,
            data=ListData(
                styles=styles,
                indent=cursor.indent
            )
        )
        
        events: List[Event] = [
            Event.enter(
                kind=BlockContainer.LIST_ITEM,
                span=cursor.new_span(
                    start=sp,
                    end=ep-1 # For checkbox, ep only points to the space after one of -, * or +
                ),
            ).with_list_styles(styles)
        ]
        cursor.advance_to(ep)

        if checkbox is not None:
            # For checkbox, its range only includes [X]
            events.append(
                Event.leaf(
                    span=cursor.new_span(
                        start=sp+2, # TODO: review if this is correct
                        end=sp+4 # the number of chars in checkbox is fixed, so we don't have to be bothered with recording mtask.end.
                    ),
                    kind=InlineLeaf.CHECKBOX,
                ).with_checkbox(checkbox==' ')
            )
            cursor.advance_to(sp+5)

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
        if not isinstance(container.data, ListData):
            return RuleResult.fail()

        if ctx.cursor.indent > container.data.indent:
            return RuleResult.continue_ok()

        if ctx.cursor.pos == ctx.cursor.eol_start:
            return RuleResult.continue_ok()

        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[Event.exit(
                kind=BlockContainer.LIST_ITEM,
                span=ctx.cursor.new_span(
                    start=ctx.cursor.pos - 1,
                    end=ctx.cursor.pos - 1,
                )
            )]
        )

class ParsedDataCell(NamedTuple):
    events: List[Event] # multiple events since a data cell could have inline elements.
    span: Range

class ParsedSeparatorCell(NamedTuple):
    event: Event # The event only spans the separator like :---:
    end_pos: int # End position of a separator cell. It could be the the end pipe, or any amount of space after ending pipe.

@dataclass
class TableRule(BlockRule):
    """
    A pipe table consists of a sequence of rows.
    Each row starts and ends with a pipe character | and
    contains one or more cells separated by pipe characters.
    | fruit  | price |
    |--------|------:|
    | apple  |  4    |
    | banana |  10   |
    """
    options: Options
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.CELLS

    def try_open(self, cursor: InputText) -> RuleResult:
        # Try to find a row.
        # m.start points to starting `|`, m.end points to EOL `\n`
        m = cursor.find_table_row()
        if not m:
            return RuleResult.fail()

        container = Container(
            rule=self,
            data=TableData(
                columns=0
            )
        )

        events: List[Event] = [
            Event.enter(
                kind=BlockContainer.TABLE,
                span=cursor.new_span(
                    start=m.start, # point to starting pipe.
                    end=m.start
                )
            )
        ]
        
        raw_row = m.captures[0] # | fruit  | price |

        row_parsed = self.parse_row(
            cursor=cursor,
            start_pipe=m.start, 
            end_pipe=m.start + len(raw_row) - 1 # ignore trailing whitespace.
        )

        # If parse table row failed, the original implementation 
        # pops the pushed Event and Container.
        # Here we return a fail flag so that EventParser will continue to try
        # another rule on current line.
        # We don't need any pop since Event and Container has never been pushed.
        if row_parsed is None:
            return RuleResult.fail()

        events.extend(row_parsed)
        
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=events,
            finished_line=True # if we successfully parsed a row, the whole line is gobbled.
        )

    
    def parse_row(
        self, 
        cursor: InputText, 
        start_pipe: int, 
        end_pipe: int
    ) -> List[Event] | None:
        """
        Parse a piped row like:

        | fruit  | price |

        Params:
            start_pos: the starting pipe.
            end_pos: the ending pipe.
        """
        rewind_point = cursor.pos # save current position to revert

        # | fruit  | price |
        events: List[Event] = [
            Event.enter(
                kind=BlockContainer.TABLE_ROW,
                span=cursor.new_span(
                    start=start_pipe,
                    end=start_pipe,
                )
            ) # |
        ]
        # The js implementation says: skip | and any initial space in the cell:
        # However, plus one only skips the starting |, not any space.
        cursor.advance() # eat starting |

        # check to see if we have a separator line
        # A table row could be either a separator row, or a data row.
        sep_found = self.parse_separator_row(cursor)
        if sep_found:
            events.extend(sep_found)
            return events

        # If the row is not parsed as separator, try to parse as data.
        # | fruit  | price |
        cells = self.parse_data_row(cursor, end_pipe)
        if cells is None:
            cursor.advance_to(rewind_point)
            return None

        # if we get here, we've parsed a table row.
        events.append(
            Event.exit(
                kind=BlockContainer.TABLE_ROW,
                span=cursor.current_span()
            )
        )
        cursor.advance_to_eol()

        return events

    def parse_data_row(self, cursor: InputText, end_pipe: int) -> Optional[List[Event]]:
        # If the row is not parsed as separator, try to parse as data.
        # | fruit  | price |
        events: List[Event] = []

        while cursor.pos <= end_pipe:
            # Parse a single cell
            cell = self.parse_data_cell(cursor)
            # If any cell parsing fails, the whole row is taken as invalid.
            if cell is None:
                # rewind, this is not a valid table row
                return None

            # cursor.pos points to ending pipe of a cell.
            events.append(
                Event.enter(
                    kind=BlockContainer.TABLE_CELL,
                    span=cursor.new_span(
                        start=cell.span.start, # the start pipe of a cell
                        end=cell.span.start,
                    )
                )
            )

            last = cell.events[-1]
            # if last cell is str
            if last.kind == InlineLeaf.STR:
                e = last.span.end
                # strip trailing space
                while cursor.src[e] == ' ' and e >= last.span.start:
                    e = e - 1
                last.span.end = e

            events.extend(cell.events)

            events.append(
                Event.exit(
                    kind=BlockContainer.TABLE_CELL,
                    span=Range(
                        start=cell.span.end, # The end pipe of a cell.
                        end=cell.span.end
                    )
                )
            )

        return events


    def parse_data_cell(self, cursor: InputText) -> ParsedDataCell | None:
        """
        Parse one cell of a table row.
        """
        inline_parser = InlineParser(
            cursor=cursor,
            options=self.options,
        )
        cell_complete = False
        # The original documentation "we start on char after |"
        # is misleading. It's not we are starting parsing from |.
        # It's a save point.
        span_start = cursor.pos - 1 # we start on char after |
        ep = span_start
        cursor.skip_space()
        while not cell_complete:
            # The match starts after previous |
            m = cursor.find_next_bar_or_tick()
            if m is None:
                cell_complete = False
                break
            # we matched a | or `+
            nextbar = m.end
            # How does this regex works? [^`|\r\n]*(?:[|]|`+)
            # | just two \| `|` | cells in this table |
            if cursor.src[nextbar] == '`' or inline_parser.in_verbatim():
                inline_parser.feed(cursor.pos, nextbar)
            elif cursor.src[nextbar-1] == '\\': # escaped |
                # This handles \|.
                # What is the string is `\\|`?
                # `\\|` means escape the backsalsh itself, then followed by a pipe.
                inline_parser.feed(cursor.pos, nextbar)
            else:
                inline_parser.feed(cursor.pos, nextbar - 1)
                ep = nextbar
                cell_complete = True # break the loop as soon as we saw first table pipe.

            self.pos = nextbar + 1

        if not cell_complete:
            return None

        cell_matches = inline_parser.get_matches()
        return ParsedDataCell(
            events=cell_matches,
            span=Range(
                start=span_start, # starting pipe
                end=ep # ending pipe
            )
        )

    def parse_separator_row(
        self,
        cursor: InputText
    ) -> Optional[List[Event]]:
        seps: List[Event] = []
        p = cursor.pos # after starting pipe.
        sep_found = False

        # Try to find all patterns like `:---: |   `.
        while not sep_found:
            cell = self.parse_separator_cell(cursor, p)
            if cell is None:
                break

            # add one separator cell.
            seps.append(cell.event) 

            # move to non-space char of next cell.
            p = cell.end_pos + 1
            
            # Break at EOL.
            # The pointer is moved in this way:
            # (:?)--*(:?)([ \t]*\|[ \t]*)
            # cell.end_pos point to the ending pipe, or any trailing space.
            # If this is the last cell, cell.end_pos + 1 should points
            # to the start of EOL, \r or \n.
            if p == cursor.eol_start:
                sep_found = True
                break

        if not sep_found:
            return None

        seps.append(Event.exit(
            kind=BlockContainer.TABLE_ROW,
            span=cursor.new_span(
                start=cursor.eol_start - 1,
                end=cursor.eol_start - 1
            ),
        ))
        cursor.advance_to_eol()
        
        return seps

    def parse_separator_cell(self, cursor: InputText, search_start: int) -> ParsedSeparatorCell | None:
        m = cursor.find_table_row(search_start)
        if m is None:
            return None

        left = m.captures[0] # left optional colon
        right = m.captures[1] # right optional colon
        trailing = m.captures[2] # trailing pipe surrouned by space
        align = Alignment.DEFAULT
        if len(left) > 0 and len(right) > 0:
            align = Alignment.CENTER
        elif len(right) > 0:
            align = Alignment.RIGHT
        elif len(left) > 0:
            align = Alignment.LEFT

        # Each cell produces an event.
        event = Event.leaf(
            span=cursor.new_span(
                start=m.start,
                end=m.end - len(trailing) # Pipe is dropped. Keep only the :---: portion
            ),
            kind=InlineLeaf.TABLE_SEPARATOR,
        ).with_table_alignment(align)

        return ParsedSeparatorCell(
            event=event,
            end_pos=m.end
        ) # Returns event and current match end index.
    

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        m = ctx.cursor.find_table_row()
        if not m:
            return RuleResult.fail()

        rawrow = m.captures[0] # | fruit  | price |
        parsed_row = self.parse_row(
            cursor=ctx.cursor,
            start_pipe=m.start,
            end_pipe=m.start + len(rawrow) - 1
        )

        if parsed_row is None:
            return RuleResult.fail()

        return RuleResult(
            status=FlowControl.CONTINUE,
            events=parsed_row,
            finished_line=True
        )

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[Event.exit(
                kind=BlockContainer.TABLE,
                span=ctx.cursor.current_span()
            )]
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
        ch = cursor.next_char()
        if ch is None:
            return RuleResult.fail()
        
        if ord(ch) != 123: # {
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

@dataclass
class FencedDivRule(BlockRule):
    """
    A div begins with a line of three or more colons,
    optionally followed by white space and a class name
    (but nothing else).
    It ends with a line of consecutive colons at least
    as long as the opening fence, or with the end of the document
    or containing block.
    The contents of a div are interpreted as block-level content.

    ::: waning
    Here is a paragraph.

    And here is another.
    :::
    """

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.BLOCK

    def try_open(self, cursor: InputText) -> RuleResult:

        # Find at least 3 colons, following by optional space.
        m = cursor.find_div_fence_start()
        if not m:
            return RuleResult.fail()

        colons = m.captures[0]

        # After space, try to find any optional word (captured),
        # followed by optinal space, followying by newline.
        m2 = cursor.find_div_fence_end(m.end+1)
        if not m2:
            return RuleResult.fail()

        clsp = m2.start # class name start position
        lang = m2.captures[0]

        container = Container(
            rule=self,
            data=FencedDivData(
                colons=len(colons),
                span=None
            )
        )

        events: List[Event] = [
            Event.enter(
                cursor.new_span(m.start, m.end),
                kind=BlockContainer.DIV
            ) # :::
        ]
        if len(lang) > 0:
            events.append(
                Event.attr(
                    kind=AttrKind.CLASS,
                    span=cursor.new_span(
                        clsp,
                        clsp + len(lang) - 1, 
                    )
                )
            )

        cursor.advance_to(m2.end + 1) # after \n

        return RuleResult(
            status=FlowControl.OPEN,
            events=events,
            container=container,
            finished_line=True,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        """The lifecycle of state-driven vs syntax-drive elements
        
        Fenced div (or code block) is syntactically difference from other elements.

        Containers likes table, list, paragraph do not have explicit closure symbol. 
        You don't know they are terminated until you see a new element. 
        That is, they don't know they are dead until new element is born.
        That's why then are closed mostly in `on_close` method: you have
        no way to figure out whether a container reached its end of life
        until you are ready to push a new sibling container.
        It's similar to how UI view works on iOS (or Android): a view does
        not know it might be destroyed until a new view is pushed on stack,
        hence `viewWillDisappear` triggered.
        For such elmenents, `try_continue` (or `continue`) of the container 
        could only tell whether it should yield to inner element or
        stop immediately.
        They could never tell whether they reached the end of life because
        there are no such markup for such hints.

        However, fenced div and code block are one of few exceptions with
        a clear physical border declaring itself "I find myself reaching the end of life". `try_continue` could detect whether it should
        close itself in addition to yielding to inner element or stopping immediately:

        - CONTINUE means go ahead to search for inner containers
        - FAIL means you cannot go deeper
        - CLOSE means a clear ending markup is found

        However, the FAIL state could actually never happen based on
        the fenced div syntax: once a fenced div opens, it could reach
        the EOF if no explicit close markup is found.
        This is why the `on_close` method is still needed.
        """
        # If ::: is inside a clode block.
        # isinstance(container.rule, CodeBlockRule) is not the corret way
        # if you follow the djot.js implementation.
        # In djot.js, the receiver and parameter might be different containers.
        # Here the archetecture has fixed this language-specific issue:
        # the passed in `container` is always used for fenced div.
        # What we are actaully trying to figure out is if current container
        # is fenced div, and it contains a deeper container code block,
        # current container find a ::: symbol, it should yield to code block.
        if ctx.is_covered:
            return RuleResult.continue_ok() # see #109

        # Now you do not have code block as innner node.
        # Go ahead as usuall.
        m = ctx.cursor.find_div_fence()

        # If ending ::: is not found, go to deeper nodes.
        # This is contray to elements without closing syntax,
        # which fails to continue as soon as the match fails.
        # Here, it the match failed, it means we havn't found
        # any closing markup for current fenced div.
        # So we should yield to inner nodes.
        if not m:
            return RuleResult.continue_ok()

        # If data attached is not FencedDivData.
        # This should not happen but typing needs the guard.
        if not isinstance(container.data, FencedDivData):
            return RuleResult.continue_ok()

        colons = m.captures[0]
        # Why do we save the ending symbol span?
        # Because here we should actually signal that the fence div is closed!
        # However, in original djot.js implementation, it always delegate
        # to the close method for cleanup.
        if len(colons) >= container.data.colons:
            container.data.span = Range(
                start=m.start,
                end=m.start + len(colons) - 1
            )
            ctx.cursor.advance_to(m.end) # \n
            return RuleResult.fail() # TODO: change to FlowControl.CLOSE?

        return RuleResult.continue_ok()

    def on_close(
        self,
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        sp = ctx.cursor.pos
        ep = ctx.cursor.pos
        if isinstance(container.data, FencedDivData):
            if container.data.span:
                sp = container.data.span.start
                ep = container.data.span.end

        event = Event.exit(
            kind=BlockContainer.DIV,
            span=ctx.cursor.new_span(sp, ep)
        )

        if sp == ep:
            print('Unclosed div', ctx.cursor.pos)

        return RuleResult(
            status=FlowControl.CLOSE,
            events=[event],
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

        

        