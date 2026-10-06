from dataclasses import dataclass, field
from typing import List, NamedTuple, Optional

from ..input import InputText, MatchedRange
from ..inline import InlineParser
from ..event import (
    BlockContainer,
    Alignment,
    Event,
    InlineLeaf,
)
from ..common import Range

from .container import (
    ContainerCap,
    Container,
    TableData,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)



class ParsedCell(NamedTuple):
    events: List[Event] # multiple events since a data cell could have inline elements.
    span: Range

class ParsedSeparatorCell(NamedTuple):
    event: Event # The event only spans the separator like :---:
    end_pos: int # End position of a separator cell. It could be the the end pipe, or any amount of space after ending pipe.


class SepInfo(NamedTuple):
    align: Alignment
    sep_start: int
    sep_end: int
    next_start: int

    @classmethod
    def new(cls, m: MatchedRange) -> 'SepInfo':
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

        return cls(
            align=align,
            sep_start=m.start,
            sep_end=m.end - len(trailing), # trim pipe surrouned by space
            next_start=m.end+1
        )

def parse_separator_row(
    cursor: InputText,
    span: Range, # | :---:  | :---: |
) -> Optional[List[Event]]:
    
    events: List[Event] = [
        Event.enter(
            kind=BlockContainer.TABLE_ROW,
            span=cursor.new_span(
                start=span.start,
                end=span.start,
            )
        ) # |
    ]

    search_start = span.start
    if cursor.is_pipe(search_start):
        search_start += 1 # after starting pipe.

    sep_found = False

    # Try to find all patterns like `:---: |   `.
    while not sep_found:
        # If
        m = cursor.find_table_sep_cell(search_start)
        if m is None:
            break

        minfo = SepInfo.new(m)
        event = Event.leaf(
            span=cursor.new_span(
                start=minfo.sep_start,
                end=minfo.sep_end # Drop everything after :---:
            ),
            kind=InlineLeaf.TABLE_SEPARATOR,
        ).with_table_alignment(minfo.align)

        # add one separator cell.
        events.append(event) 

        # move to non-space char of next cell.
        search_start = minfo.next_start
        
        # Break at EOL.
        # The pointer is moved in this way:
        # :---: \t | \t
        # If this is the last cell, cell.end_pos + 1 should points
        # to the start of EOL, \r or \n.
        if search_start == cursor.line_end:
            sep_found = True
            break

    if not sep_found:
        return None

    events.append(Event.exit(
        kind=BlockContainer.TABLE_ROW,
        span=cursor.new_span(
            start=cursor.line_end - 1,
            end=cursor.line_end - 1
        ),
    ))
    
    return events

def scan_table_pipe(cursor: InputText, startpos: int, endpos: int) -> Optional[int]:
    i = startpos
    in_verbatim = False
    verbatim_ticks = 0

    while i <= endpos:
        ch = cursor.src[i]

        if ch in '\r\n':
            return None

        if ch == '\\' and not in_verbatim:
            i += 2
            continue

        if ch == '`':
            ticks = cursor.count_char('`', i)
            if not in_verbatim:
                in_verbatim = True
                verbatim_ticks = ticks
            elif ticks == verbatim_ticks:
                in_verbatim = False
            i += ticks
            continue

        if ch == '|' and not in_verbatim:
            return i

        i += 1

    return None

def parse_data_cell(inline_parser: InlineParser, pipe_start: int, limit: int) -> Optional[int]:
    """
    Parse one cell of a table row.
    """
    # The original documentation "we start on char after |"
    # is misleading. It's not we are starting parsing from |.
    # It's a save point.

    search_start = pipe_start + 1 # after pipe

    search_start = inline_parser.state.cursor.skip_space_from(search_start)

    nextbar = scan_table_pipe(
        inline_parser.state.cursor,
        search_start,
        limit
    )

    if not nextbar:
        return None

    inline_parser.feed(search_start, nextbar-1)

    return nextbar

def parse_data_row(
    cursor: InputText,
    span: Range, # | fruit  | price |
) -> Optional[List[Event]]:
    
    events: List[Event] = [
        Event.enter(
            kind=BlockContainer.TABLE_ROW,
            span=cursor.new_span(
                start=span.start,
                end=span.start,
            )
        ) # |
    ]

    pipe_start = span.start

    inline_parser = InlineParser(
        cursor=cursor,
    )

    while pipe_start < span.end:
        # Parse a single cell
        inline_parser.state.push_event(
            Event.enter(
                kind=BlockContainer.TABLE_CELL,
                span=cursor.new_span(
                    start=pipe_start, # the start pipe of a cell
                    end=pipe_start,
                )
            )
        )
        nextbar = parse_data_cell(inline_parser, pipe_start, span.end)
        # If any cell parsing fails, the whole row is taken as invalid.
        if nextbar is None:
            # rewind, this is not a valid table row
            return None

        inline_parser.state.trim_last_space(pop_empty=False)

        inline_parser.state.push_event(
            Event.exit(
                kind=BlockContainer.TABLE_CELL,
                span=cursor.new_span(
                    start=nextbar, # The end pipe of a cell.
                    end=nextbar
                )
            )
        )

        pipe_start = nextbar

    events.extend(inline_parser.iter_merged_events())
        

    # if we get here, we've parsed a table row.
    events.append(
        Event.exit(
            kind=BlockContainer.TABLE_ROW,
            span=cursor.new_span(
                start=span.end+1,
                end=span.end+1,
            )
        )
    )

    return events


def parse_row(
    cursor: InputText, 
    row_span: Range,
) -> List[Event] | None:
    """
    Parse a piped row like:

    | fruit  | price |

    Params:
        start_pos: the starting pipe.
        end_pos: the ending pipe.
    """

    # The js implementation says: skip | and any initial space in the cell:
    # However, plus one only skips the starting |, not any space.

    # check to see if we have a separator line
    # A table row could be either a separator row, or a data row.
    sep_events = parse_separator_row(cursor, span=row_span)
    if sep_events:
        return sep_events

    # If the row is not parsed as separator, try to parse as data.
    # | fruit  | price |
    data_events = parse_data_row(cursor, span=row_span)
    if data_events is None:
        return None

    return data_events

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
    
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.CELLS

    def try_open(self, cursor: InputText) -> RuleResult:
        # Try to find a row.
        # m.start points to starting `|`, m.end points to EOL `\n`
        # From cursor.pos, search pattern: r'(\|[^\r\n]*\|)[ \t]*\r?\n'
        m = cursor.find_table_row()
        if not m:
            return RuleResult.fail()

        container = Container(
            rule=self,
            data=TableData(
                columns=0
            ),
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.line_end, cursor.line_end)
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

        row_parsed = parse_row(
            cursor=cursor,
            row_span=Range(
                start=m.start, # save as cursor.pos
                end=m.start + len(raw_row) - 1 # ignore trailing whitespace.
            ),
        )

        # If parse table row failed, the original implementation 
        # pops the pushed Event and Container.
        # Here we return a fail flag so that EventParser will continue to try
        # another rule on current line.
        # We don't need any pop since Event and Container has never been pushed.
        if row_parsed is None:
            return RuleResult.fail()

        events.extend(row_parsed)
        print(f'Row events: {len(events)}')

        # cursor.advance_to_eol()
        next_pos = cursor.line_end
        
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=events,
            finished_line=True, # if we successfully parsed a row, the whole line is gobbled.
            next_pos=next_pos
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        m = ctx.cursor.find_table_row()
        if not m:
            return RuleResult.fail()

        rawrow = m.captures[0] # | fruit  | price |
        parsed_row = parse_row(
            cursor=ctx.cursor,
            row_span=Range(m.start, m.start+len(rawrow)-1),
        )

        if parsed_row is None:
            return RuleResult.fail()

        container.update_closing_boundary(ctx.cursor.line_end, ctx.cursor.line_end)

        return RuleResult(
            status=FlowControl.CONTINUE,
            events=parsed_row,
            finished_line=True,
            next_pos=ctx.cursor.line_end,
        )

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        assert container.closing_boundary is not None
        return RuleResult(
            status=FlowControl.CLOSE,
            events=[Event.exit(
                kind=BlockContainer.TABLE,
                span=ctx.cursor.new_span(
                    container.closing_boundary.start,
                    container.closing_boundary.end,
                )
            )]
        )