import copy
from dataclasses import dataclass
from typing import List

from ..cursor import Cursor
from ..event import (
    BlockContainer,
    Event,
    InlineLeaf,
)
from ..common import Range

from .container import ContainerCap
from .frame import (
    BlockFrame,
    FootnoteData,
    OpenStatus,
    BlockRule,
    OpenResult,
    ContinueResult,
    ContinueAction,
    ParsingContext,
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

    def try_open(self, cursor: Cursor) -> OpenResult:

        start = cursor.pos
        token = cursor.find_footnote_def(start, cursor.line_end)
        if token is None:
            return OpenResult.not_matched()

        container = BlockFrame(
            rule=self,
            data=FootnoteData(
                label=token.label,
                indent=cursor.indent,
            ),
            start_pos=start,
            closing_boundary=Range(start, cursor.line_end)
        )
        events = [
            Event.enter( # [
                kind=BlockContainer.FOOTNOTE,
                span=cursor.new_span(
                    start=start,
                    end=start,
                ),
            ), 
            Event.leaf( # foo
                kind=InlineLeaf.NOTE_LABEL,
                span=copy.copy(token.label_span)
            ) 
        ]

        cursor.advance_pos(token.end_pos) # move to first space
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
        if not isinstance(frame.data, FootnoteData):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        if ctx.cursor.indent > frame.data.indent or ctx.cursor.pos == ctx.cursor.line_end: # line start or line end
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
                kind=BlockContainer.FOOTNOTE,
                span=ctx.cursor.new_span(
                    frame.closing_boundary.start,
                    frame.closing_boundary.end,
                )
            )
        ]
