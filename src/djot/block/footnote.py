from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
    InlineLeaf,
)

from .container import (
    ContainerCap,
    Container,
    FootnoteData,
    FlowControl,
    BlockRule,
    RuleResult,
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
