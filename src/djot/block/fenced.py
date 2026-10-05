from dataclasses import dataclass
from typing import List

from ..input import InputText
from ..event import (
    BlockContainer,
    AttrKind,
    Event,
)
from ..logger import logger

from .container import (
    ContainerCap,
    Container,
    FencedDivData,
    FlowControl,
    BlockRule,
    RuleResult,
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
            ),
            start_pos=cursor.pos,
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

        next_pos = m2.end + 1 # after \n

        return RuleResult(
            status=FlowControl.OPEN,
            events=events,
            container=container,
            finished_line=True,
            next_pos=next_pos,
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
            container.update_closing_boundary(
                m.start,
                m.start + len(colons) - 1
            )
            
            next_pos = m.end # \n
            return RuleResult(
                status=FlowControl.STOP,
                next_pos=next_pos,
            )

        return RuleResult.continue_ok()

    def on_close(
        self,
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        sp = ctx.cursor.pos
        ep = ctx.cursor.pos

        if container.closing_boundary:
            sp = container.closing_boundary.start
            ep = container.closing_boundary.end

        event = Event.exit(
            kind=BlockContainer.DIV,
            span=ctx.cursor.new_span(sp, ep)
        )

        if sp == ep:
            logger.debug(f'Unclosed div at {ctx.cursor.pos}')

        return RuleResult(
            status=FlowControl.CLOSE,
            events=[event],
        )