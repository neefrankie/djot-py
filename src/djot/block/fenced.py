import copy
from dataclasses import dataclass
from typing import List

from ..cursor import Cursor
from ..event import (
    BlockContainer,
    AttrKind,
    Event,
)
from ..logger import logger

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
)



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

    def try_open(self, cursor: Cursor) -> OpenResult:

        # Find at least 3 colons, following by optional space.
        token = cursor.find_div_start(cursor.pos)

        if token is None:
            return OpenResult.not_matched()

        container = BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            div_colon=token.colons
        )

        events: List[Event] = [
            Event.enter(
                copy.copy(token.colon_span),
                kind=BlockContainer.DIV
            ) # :::
        ]

        if token.lang_span is not None:
            events.append(
                Event.attr(
                    kind=AttrKind.CLASS,
                    span=copy.copy(token.lang_span)
                )
            )

        cursor.advance_pos(cursor.line_end) # after \n

        return OpenResult(
            status=OpenStatus.MATCH_AND_CONSUMED,
            events=events,
            frame=container,
        )

    def on_continue(
        self,
        frame: BlockFrame,
        ctx: ParsingContext
    ) -> ContinueResult:
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
            return ContinueResult(
                frame_action=FrameAction.PRESERVE,
            ) # see #109

        # Now you do not have code block as innner node.
        # Go ahead as usual.

        # If ending ::: is not found, go to deeper nodes.
        # This is contray to elements without closing syntax,
        # which fails to continue as soon as the match fails.
        # Here, it the match failed, it means we havn't found
        # any closing markup for current fenced div.
        # So we should yield to inner nodes.

        if not frame.div_colon:
            return ContinueResult(
                frame_action=FrameAction.PRESERVE,
            )
        
        start_pos = ctx.cursor.pos
        span = ctx.cursor.find_div_end(start_pos, frame.div_colon)
        
        if span is None:
            return ContinueResult(
                frame_action=FrameAction.PRESERVE,
            )


        # Why do we save the ending symbol span?
        # Because here we should actually signal that the fence div is closed!
        # However, in original djot.js implementation, it always delegate
        # to the close method for cleanup.
        frame.update_closing_boundary(
            span.start,
            span.end
        )
        
        ctx.cursor.advance_pos(ctx.cursor.line_end) # \n
        return ContinueResult(
            frame_action=FrameAction.IMPLICIT_CLOSE,
            line_action=LineAction.CONSUMED,
            # TODO: can we emit events here?
        )


    def on_close(
        self,
        frame: BlockFrame, 
        ctx: ParsingContext,
    ) -> List[Event]:
        sp = ctx.cursor.pos
        ep = ctx.cursor.pos

        if frame.closing_boundary:
            sp = frame.closing_boundary.start
            ep = frame.closing_boundary.end

        event = Event.exit(
            kind=BlockContainer.DIV,
            span=ctx.cursor.new_span(sp, ep)
        )

        if sp == ep:
            logger.debug(f'Unclosed div at {ctx.cursor.pos}')

        return [event]