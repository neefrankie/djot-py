from dataclasses import dataclass
from typing import List

from djot.cursor import Cursor
from djot.attributes import (
    AttributeParser,
    AttrStatus,
)
from djot.event import (
    Event,
    BlockContainer,
)
from djot.common import Range
from djot.inline import InlineParser
from djot.logger import logger

from .container import ContainerCap
from .frame import (
    BlockFrame,
    OpenStatus,
    BlockRule,
    OpenResult,
    ContinueResult,
    FrameAction,
    LineAction,
    ParsingContext,
    BlockAttrContext,
)


@dataclass
class AttributeRule(BlockRule):

    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.ATTRIBUTES

    def try_open(self, cursor: Cursor) -> OpenResult:      
        if not cursor.is_left_brace(cursor.pos):
            return OpenResult(
                status=OpenStatus.NOT_MATCHED,
            )

        start = cursor.pos
        attribute_parser = AttributeParser(cursor)

        res = attribute_parser.feed(start, cursor.line_end)

        logger.debug(f'## {start}: Attribute parse result: {res}\n')

        match res.status:            
            case AttrStatus.FAIL:
                # FAIL might be caused by invalid attributes,
                # or a line started with inline markup like:
                # {+ADD ME!+}
                return OpenResult(
                    status=OpenStatus.NOT_MATCHED,
                )

            case AttrStatus.DONE:
                # Attributes should stand alone on a line.
                if not cursor.is_ahead_blank(res.position + 1):
                    logger.debug(f'{res.position}: block attributes has contents followed')
                    return OpenResult(
                        status=OpenStatus.NOT_MATCHED,
                    )
                
                # A single line attributes
                events = self._handle_done(
                    start=cursor.new_span(start, start),
                    end=cursor.new_span(
                        start=res.position,
                        end=res.position
                    ),
                    attr_events=attribute_parser.events
                )

                cursor.advance_pos(cursor.line_end) # move directly to EOL to prevent generating redundant events.
                        
                return OpenResult(
                    status=OpenStatus.MATCH_AND_CONSUMED,
                    events=events,
                )

            case AttrStatus.CONTINUE:
                # Only CONTINUE state needs the try_continue method.
                frame = BlockFrame(
                    rule=self,
                    start_pos=start,
                    closing_boundary=Range(cursor.line_end, cursor.line_end),
                    block_attr=BlockAttrContext(
                        status=res.status,
                        indent=cursor.indent,
                        start_pos=start,
                        slices=[
                            Range(start, cursor.line_end)
                        ],
                    ),
                    attribute_parser=attribute_parser,
                )

                cursor.advance_pos(cursor.line_end)
                return OpenResult(
                    status=OpenStatus.MATCH_AND_CONSUMED,
                    frame=frame,
                )

    def _handle_done(self, start: Range, end: Range, attr_events: List[Event]) -> List[Event]:
        events = [
            Event.enter(
                span=start,
                kind=BlockContainer.ATTRIBUTES
            )
        ]

        events.extend(attr_events)

        events.append(
            Event.exit(
                kind=BlockContainer.ATTRIBUTES,
                # NOTE: djot.js implementation incorrectly sets the
                # block attributes to next block starting point.
                # It should be the end brace based on human intuition and symmetry.
                span=end
            )
        )

        return events


    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
        """
        There's a potential problem in a special case:

        {.bar}
        {#foo}

        In the first line, you created a frame and pushed it on stack.
        Then in continue method, you set action to CLOSE and line_action to CONSUMED.
        When it comes to the second line, it will try this frame's continue mmethod.
        It find out it should close so it stops and pop all frame from this one.
        And then it find out line_action is consumed, so it will jump directly to the next line.
        No open is even tried for the second line.

        The solution is never creating a frame if you are sure you have finished a block in open stage.
        """
        if frame.block_attr is None:
            return ContinueResult(
                frame_action=FrameAction.IMPLICIT_CLOSE,
            )

        # Only CONTINUE state cound be carried over to this stage.
        if frame.block_attr.status != AttrStatus.CONTINUE:
            return ContinueResult(
                frame_action=FrameAction.IMPLICIT_CLOSE,
            )

        if frame.attribute_parser is None or ctx.cursor.indent <= frame.block_attr.indent:
            logger.debug(f'{self.__class__.__name__} continue failed: not enough indent')
            # Current line must be indented more than starting line.
            # Otherwise continue should fail and previously parsed
            # spans should rewind.
            # NOTE:
            # When we are here, previous line must resulted to
            # status == AttrStatus.CONTINUE.
            # However, FrameAction.FALLBACK will result to
            # the on_close method called.
            # If we do not change status to FAIL,
            # the on_close method will create perform reparsing,
            # which is not what we want.
            frame.block_attr.status = AttrStatus.FAIL
            return ContinueResult(
                frame_action=FrameAction.FALLBACK,
            )

        logger.debug(f'{ctx.cursor.pos}: AttributeRule continueed')

        start = ctx.cursor.pos
        line_end = ctx.cursor.line_end

        frame.block_attr.slices.append(Range(
            start=start,
            end=line_end,
        ))

        # For continue, we shuld carry over the last ending points to on_close method.
        # For done, we don't need it.
        # Foa fail, we have to include current line.
        frame.update_closing_boundary(line_end, line_end)

        res = frame.attribute_parser.feed(start, line_end)
    
        match res.status:
            case AttrStatus.FAIL:
                frame.block_attr.status = AttrStatus.FAIL
                return ContinueResult(
                    frame_action=FrameAction.FALLBACK, # fallback includes current line.
                )

            case AttrStatus.CONTINUE:
                frame.block_attr.status = AttrStatus.CONTINUE

                ctx.cursor.advance_pos(ctx.cursor.line_end)

                return ContinueResult(
                    frame_action=FrameAction.PRESERVE,
                    line_action=LineAction.CONSUMED,
                )

            
            case AttrStatus.DONE:
                # This indicates previous line is attribute-like,
                # and continue to this line, and initially parsed
                # to attribute end, but then find out this line
                # has trailing content.
                # So previous line should not be treated as attribute.py
                # In such case we should immediately close current frame.
                if not ctx.cursor.is_ahead_blank(res.position + 1):
                    frame.block_attr.status = AttrStatus.FAIL
                    return ContinueResult(
                        frame_action=FrameAction.FALLBACK, # fallback includes current line.
                    )

                events = self._handle_done(
                    start=ctx.cursor.new_span(
                        frame.block_attr.start_pos,
                        frame.block_attr.start_pos
                    ),
                    end=ctx.cursor.new_span(
                        start=res.position,
                        end=res.position,
                    ),
                    attr_events=frame.attribute_parser.events.copy()
                )

                frame.block_attr.status = AttrStatus.DONE
                ctx.cursor.advance_pos(ctx.cursor.line_end)

                return ContinueResult(
                    frame_action=FrameAction.EXPLICIT_CLOSE,
                    line_action=LineAction.CONSUMED,
                    events=events,
                )


    def on_close(
        self, 
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        if frame.block_attr is None:
            return []

        # DONE and FAIL state are handled in open
        # or continue stage, so they shouldn't fallthough to here.
        # When attribute frame should close but it
        # is still in CONTINUE state, it means it
        # never see ending token.
        # So the whole block is not valid attribute.
        if frame.block_attr.status != AttrStatus.CONTINUE:
            return []

        start_pos = frame.block_attr.start_pos
        events: List[Event] = [
            Event.enter(
                kind=BlockContainer.PARA,
                span=ctx.cursor.new_span(
                    start=start_pos,
                    end=start_pos,
                )
            )
        ]

        # In djot.js, the addContainer method has a parameter called skipCloseUnmatched.
        # I think it is reserved specfically for usage here, creating a paragraph container
        # without causing side-effect.

        inline_parser = InlineParser(ctx.cursor)

        inline_parser.reparse_attributes(frame.block_attr.slices)

        events.extend(inline_parser.iter_merged_events())

        assert frame.closing_boundary is not None

        events.append(
            Event.exit(
                kind=BlockContainer.PARA,
                span=Range(
                    start=frame.closing_boundary.start,
                    end=frame.closing_boundary.end,
                )
            )
        )

        return events

        

        
