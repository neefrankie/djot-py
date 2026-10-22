from typing import List
from dataclasses import dataclass
from typing import List

from djot.input import InputText
from djot.event import (
    BlockContainer,
    Event,
    InlineLeaf,
)
from djot.logger import logger
from djot.common import Range
from djot.common.list_style import (
    parse_list_styles,
    intersect_list_styles
)

from .container import (
    ContainerCap,
    BlockFrame,
    ListData,
    OpenStatus,
    BlockRule,
    OpenResult,
    ContinueResult,
    ContinueAction,
    ParsingContext,
)

@dataclass
class ListRule(BlockRule):
    """
    A list is simply a sequence of list items of the same type.
    Changing ordered list style or bullet will stop one list and start a new one.
    """
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.LIST_ITEM

    def try_open(self, cursor: InputText) -> OpenResult:
        m = cursor.find_list_marker() # matches the marker followed by a whitespace.
        if not m:
            return OpenResult.not_matched()
        start_pos = m.start
        end_pos = m.end # whitespace
        marker = cursor.src[start_pos:end_pos] # content before whitespace.
        # A bullete list item that begins with [ ], [X] or [x]
        # followed by a space is a task list item.
        # - [ ]
        # - [X]
        # - [x]
        # 01234
        mtask = cursor.find_task_list_marker()
        if mtask is not None:
            marker = cursor.src[mtask.start:mtask.start + 5] # '- [ ]'


        styles = parse_list_styles(marker)
        logger.debug(f'⏺ styles: {styles!r}')
        if styles is None:
            return OpenResult.not_matched()
        
        container = BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.line_end, cursor.line_end),
            data=ListData(
                styles=styles,
                indent=cursor.indent
            )
        )
        # In djot.js. container is added here.
        # So anything unmatched container will
        # be closed at this cursor.pos.

        event = Event.enter(
            kind=BlockContainer.LIST,
            span=cursor.new_span(
                start=start_pos,
                end=end_pos - 1, # ignore trailing space.
            ),
        ).with_list_styles(styles)

        # NOTE: cursor is not moved.
        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=container,
            events=[event],
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        if not isinstance(frame.data, ListData):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        # As long as next line is indented more than previous line,
        # keep the container.
        # - one
        #   two
        if ctx.cursor.indent > frame.data.indent:
            logger.debug(f'{ctx.cursor.pos}. ListRule.on_continue due to indentation: current indent: {ctx.cursor.indent}, previous indent: {frame.data.indent}')
            frame.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end,
            )
            return ContinueResult(
                action=ContinueAction.CONTINUE,
            )

        if ctx.cursor.is_eol_at(ctx.cursor.pos):
            logger.debug(f'{ctx.cursor.pos}. ListRule.on_continue due to blankline')
            frame.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end,
            )
            return ContinueResult(
                action=ContinueAction.CONTINUE,
            )

        m = ctx.cursor.find_list_marker()
        if m is None:
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        marker = ctx.cursor.src[m.start:m.end]
        mtask = ctx.cursor.find_task_list_marker()
        if mtask is not None:
            marker = ctx.cursor.src[mtask.start:mtask.start + 5]

        # If new styles does not include previous style, drop it.
        # This plays two roles:
        # 1. narrow down styles based on later items
        # 2. stop a list if styles changed.
        incoming_styles = parse_list_styles(marker)
        newstyles = intersect_list_styles(
            frame.data.styles,
            incoming_styles
        )

        if not newstyles:
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        frame.data.styles = newstyles
        
        frame.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end,
        )
        return ContinueResult(
            action=ContinueAction.CONTINUE,
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert frame.closing_boundary is not None

        return [
            Event.exit(
                kind=BlockContainer.LIST,
                # TODO: this is a very weired behavior. In djot.js, this position is non-deterministic.
                # Most of time it ends at next line start.
                # However, at EOF, it ends at EOF.
                # A more reasonable position should always be the end of line of last list item.
                span=ctx.cursor.new_span(
                    frame.closing_boundary.start,
                    frame.closing_boundary.end
                )
            )
        ]


@dataclass
class ListItemRule(BlockRule):
    kind: ContainerCap = ContainerCap.LIST_ITEM
    accepts_content: ContainerCap = ContainerCap.BLOCK

    def try_open(self, cursor: InputText) -> OpenResult:
        """
        A list item consists of a list marker, followed by a space (or a newline)
        followed by one or more lines, indented relative to the list marker.
        """
        m = cursor.find_list_marker()
        if m is None:
            return OpenResult.not_matched()
        
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
            checkbox = cursor.src[mtask.start+3] # ' ', 'x', 'X'

        styles = parse_list_styles(marker)
        if len(styles) == 0:
            return OpenResult.not_matched()

        container = BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.line_end, cursor.line_end),
            data=ListData(
                styles=styles,
                indent=cursor.indent
            )
        )
        # TODO: Container is added at this point.
        # So previous container close point happens here!
        # You cannot rely the cursor.pos after the method finished.
        events: List[Event] = [
            Event.enter(
                kind=BlockContainer.LIST_ITEM,
                span=cursor.new_span(
                    start=sp,
                    end=ep-1 # For checkbox, ep only points to the space after one of -, * or +
                ),
            ).with_list_styles(styles)
        ]
        # cursor.advance_to(ep)
        next_pos = ep

        # - [X]
        # LISTE_ITEM
        # CHECKBOX
        # LIST_ITEM
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
            # cursor.advance_to(sp+5)
            next_pos = sp+5

        cursor.advance_pos(next_pos)

        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=container,
            events=events,
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        if not isinstance(frame.data, ListData):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        # A line indented should be taken as a continuation of previous list item.
        # - one
        #   - dash is plain text.
        if ctx.cursor.indent > frame.data.indent or ctx.cursor.is_eol_at(ctx.cursor.pos):
            logger.debug(f"{ctx.cursor.pos}. ListItem.on_continue due to indent or blankline")
            frame.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end,
            )
            return ContinueResult(
                action=ContinueAction.CONTINUE,
            )

        return ContinueResult(
            action=ContinueAction.STOP,
        )

    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert frame.closing_boundary is not None

        return [
            Event.exit(
                kind=BlockContainer.LIST_ITEM,
                span=ctx.cursor.new_span(
                    start=frame.closing_boundary.start,
                    end=frame.closing_boundary.end,
                )
            )
        ]