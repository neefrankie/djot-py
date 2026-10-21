from dataclasses import dataclass
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

    def try_open(self, cursor: InputText) -> OpenResult:
        m = cursor.find_footnote_definition()
        if m is None:
            return OpenResult.not_matched()

        # '[^foo]: '
        start_pos = m.start # [
        end_pos = m.end # space aftr :
        label = m.captures[0] # foo
        container = BlockFrame(
            rule=self,
            data=FootnoteData(
                label=label,
                indent=cursor.indent,
            ),
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.pos, cursor.line_end)
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

        cursor.advance_pos(end_pos) # move to first space
        return OpenResult(
            status=OpenStatus.MATCHED,
            frame=container,
            events=events,
        )

    def on_continue(
        self,
        container: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        if not isinstance(container.data, FootnoteData):
            return ContinueResult(
                action=ContinueAction.STOP,
            )

        if ctx.cursor.indent > container.data.indent or ctx.cursor.pos == ctx.cursor.line_end: # line start or line end
            container.update_closing_boundary(
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
        container: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        assert container.closing_boundary is not None

        return [
            Event.exit(
                kind=BlockContainer.FOOTNOTE,
                span=ctx.cursor.new_span(
                    container.closing_boundary.start,
                    container.closing_boundary.end,
                )
            )
        ]
