import copy
from typing import List
from dataclasses import dataclass
from typing import List

from djot.cursor import Cursor
from djot.event import (
    BlockContainer,
    Event,
    InlineLeaf,
)
from djot.logger import logger
from djot.common import Range
from djot.common.list_style import (
    intersect_list_styles
)

from .container import ContainerCap
from .frame import (
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

    def try_open(self, cursor: Cursor) -> OpenResult:

        token = cursor.parse_list(cursor.pos, cursor.line_end)
        if token is None:
            return OpenResult.not_matched()
        
        container = BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.line_end, cursor.line_end),
            data=ListData(
                styles=token.styles.copy(),
                indent=cursor.indent
            )
        )
        # In djot.js. container is added here.
        # So anything unmatched container will
        # be closed at this cursor.pos.

        event = Event.enter(
            kind=BlockContainer.LIST,
            span=copy.copy(token.item_span)
        ).with_list_styles(token.styles.copy())

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

        if ctx.cursor.is_newline(ctx.cursor.pos):
            logger.debug(f'{ctx.cursor.pos}. ListRule.on_continue due to blankline')
            frame.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end,
            )
            return ContinueResult(
                action=ContinueAction.CONTINUE,
            )

        token = ctx.cursor.parse_list(ctx.cursor.pos, ctx.cursor.line_end)
        if token is None:
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        # If new styles does not include previous style, drop it.
        # This plays two roles:
        # 1. narrow down styles based on later items
        # 2. stop a list if styles changed.
        incoming_styles = token.styles
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

    def try_open(self, cursor: Cursor) -> OpenResult:
        """
        A list item consists of a list marker, followed by a space (or a newline)
        followed by one or more lines, indented relative to the list marker.
        """
        token = cursor.parse_list(cursor.pos, cursor.line_end)
        if token is None:
            return OpenResult.not_matched()

        container = BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.line_end, cursor.line_end),
            data=ListData(
                styles=token.styles.copy(),
                indent=cursor.indent
            )
        )

        events: List[Event] = [
            Event.enter(
                kind=BlockContainer.LIST_ITEM,
                # '-', '(1)', '1)', '1.'
                span=copy.copy(token.item_span)
            ).with_list_styles(token.styles.copy())
        ]

        # - [X]
        if token.checkbox_span is not None:
            # For checkbox, its range only includes [X]
            events.append(
                Event.leaf(
                    kind=InlineLeaf.CHECKBOX,
                    span=copy.copy(token.checkbox_span),
                ).with_checkbox(token.checker==' ')
            )

        cursor.advance_pos(token.end)

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
        if ctx.cursor.indent > frame.data.indent or ctx.cursor.is_newline(ctx.cursor.pos):
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