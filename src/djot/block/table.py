from dataclasses import dataclass
from typing import List, NamedTuple, Optional

from ..input import InputText
from ..inline import InlineParser
from ..event import (
    BlockContainer,
    Alignment,
    Event,
    InlineLeaf,
)
from ..common import Range
from ..options import Options

from .container import (
    ContainerCap,
    Container,
    TableData,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
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
            if cursor.src[nextbar] == '`' or inline_parser.in_verbatim:
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

        cell_matches = list(inline_parser.iter_merged_events())
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