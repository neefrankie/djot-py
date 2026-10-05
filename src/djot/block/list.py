import re
from typing import List
from dataclasses import dataclass
import re
from typing import List

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
    InlineLeaf,
)
from ..logger import logger
from ..common import Range

from .container import (
    ContainerCap,
    Container,
    ListData,
    FlowControl,
    BlockRule,
    RuleResult,
    ParsingContext,
)

_re_task_list_item = re.compile(r'^[+*-] \[[Xx ]\]')
# 1. ordered, decimal-enumerated, followed by period
# 1) ordered, decimal-enumerated, followed by parenthesis
# (1) ordered, decimal-enumerated, enclosed in parentheses
_re_decimal_item = re.compile(r'^[(]?[0-9]+[).]')
_re_decimal_multiple = re.compile(r'[0-9]+')
# a. ordered, lower-alpha-enumerated, followed by period
# a) ordered, lower-alpha-enumerated, followed by parenthesis
# (a) ordered, lower-alpha-enumerated, enclosed in parentheses
# i. 
# i)
# (i)
_re_lower_roman_alpha_item = re.compile(r'^[(]?[ivxlcdm][).]')
_re_lower_alpha_multiple = re.compile(r'[a-z]+')

# A. ordered, upper-alpha-enumerated, followed by period
# A) ordered, upper-alpha-enumerated, followed by parenthesis
# (A) ordered, upper-alpha-enumerated, enclosed in parentheses
# I. ordered, upper-roman-enumerated, followed by period
# I) ordered, upper-roman-enumerated, followed by parenthesis
# (I) ordered, upper-roman-enumerated, enclosed in parentheses
_re_upper_roman_alpha_item = re.compile(r'^[(]?[IVXLCDM][).]')
_re_upper_alpha = re.compile(r'[A-Z]+')

_re_lower_roman_item = re.compile(r'^[(]?[ivxlcdm]+[).]')
_re_upper_roman_item = re.compile(r'^[(]?[IVXLCDM]+[).]')

# a. 
# a) 
# (a) 
_re_lower_alpha_item = re.compile(r'^[(]?[a-z][).]')
_re_lower_alpha_single = re.compile(r'[a-z]')

# A. ordered, upper-alpha-enumerated, followed by period
# A) ordered, upper-alpha-enumerated, followed by parenthesis
# (A) ordered, upper-alpha-enumerated, enclosed in parentheses
_re_upper_alpha_item = re.compile(r'^[(]?[A-Z][).]')
_re_upper_alpha_single = re.compile(r'[A-Z]')

def get_list_styles(marker: str) -> List[str]:
    if marker == '+' or marker == '-' or marker == '*' or marker == ':':
        return [marker]
    elif _re_task_list_item.search(marker):
        return [marker[0] + "X"] # task list - include marker for consistency
    elif _re_decimal_item.search(marker):
        return [_re_decimal_multiple.sub('1', marker)]
    elif _re_lower_roman_alpha_item.search(marker):
        return [
            _re_lower_alpha_multiple.sub('i', marker),
            _re_lower_alpha_multiple.sub('a', marker)
        ]
    elif _re_upper_roman_alpha_item.search(marker):
        return [
            _re_upper_alpha.sub('I', marker),
            _re_upper_alpha.sub('A', marker)
        ]
    elif _re_lower_roman_item.search(marker):
        return [_re_lower_alpha_multiple.sub('i', marker)]
    elif _re_upper_roman_item.search(marker):
        return [_re_upper_alpha.sub('I', marker)]
    elif _re_lower_alpha_item.search(marker):
        return [_re_lower_alpha_single.sub('a', marker)]
    elif _re_upper_alpha_item.search(marker):
        return [_re_upper_alpha_single.sub('A', marker)]
    else:
        return []





@dataclass
class ListRule(BlockRule):
    """
    A list is simply a sequence of list items of the same type.
    Changing ordered list style or bullet will stop one list and start a new one.
    """
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.LIST_ITEM

    def try_open(self, cursor: InputText) -> RuleResult:
        m = cursor.find_list_marker() # matches the marker followed by a whitespace.
        if not m:
            return RuleResult.fail()
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

        # ['+'], ['-'], ['*'], [':']
        # ['-X']
        # ['(1)'], ['1.'], ['1)']
        # ['(i)', '(a)'], ['i.', 'a.'], ['i)', 'a)']
        # ['(I)', '(A)'], ['I.', 'A.'], ['I)', 'A)']
        # ['(i)'], ['i.'], ['i)']
        # ['(I)'], ['I.'], ['I)']
        # ['(a)'], ['a.'], ['a)']
        # ['(A)'], ['A.'], ['A)']
        styles = get_list_styles(marker)
        logger.debug(f'⏺ styles: {styles}')
        if len(styles) == 0:
            return RuleResult.fail()
        
        container = Container(
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
        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=[event],
            next_pos=cursor.pos,
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        if not isinstance(container.data, ListData):
            return RuleResult.fail()

        if ctx.cursor.indent > container.data.indent:
            container.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end,
            )
            return RuleResult.continue_ok()

        if ctx.cursor.is_eol_at(ctx.cursor.pos):
            container.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end,
            )
            return RuleResult.continue_ok()

        m = ctx.cursor.find_list_marker()
        if m is None:
            return RuleResult.fail()

        marker = ctx.cursor.src[m.start:m.end]
        mtask = ctx.cursor.find_task_list_marker()
        if mtask is not None:
            marker = ctx.cursor.src[mtask.start:mtask.start + 5]

        styles = get_list_styles(marker)
        
        newstyles: List[str] = []
        for prev_style in container.data.styles:
            if prev_style in styles:
                newstyles.append(prev_style)

        if not newstyles:
            return RuleResult.fail()

        container.data.styles = newstyles
        
        container.update_closing_boundary(
            ctx.cursor.line_end,
            ctx.cursor.line_end,
        )
        return RuleResult.continue_ok()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        assert container.closing_boundary is not None

        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.LIST,
                    # TODO: this is a very weired behavior. In djot.js, this position is non-deterministic.
                    # Most of time it ends at next line start.
                    # However, at EOF, it ends at EOF.
                    # A more reasonable position should always be the end of line of last list item.
                    span=ctx.cursor.new_span(
                        container.closing_boundary.start,
                        container.closing_boundary.end
                    )
                )
            ]
        )


@dataclass
class ListItemRule(BlockRule):
    kind: ContainerCap = ContainerCap.LIST_ITEM
    accepts_content: ContainerCap = ContainerCap.BLOCK

    def try_open(self, cursor: InputText) -> RuleResult:
        """
        A list item consists of a list marker, followed by a space (or a newline)
        followed by one or more lines, indented relative to the list marker.
        """
        m = cursor.find_list_marker()
        if m is None:
            return RuleResult.fail()
        
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
            checkbox = cursor.src[mtask.start+3:mtask.start+4] # X

        styles = get_list_styles(marker)
        if len(styles) == 0:
            return RuleResult.fail()

        container = Container(
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

        return RuleResult(
            status=FlowControl.OPEN,
            container=container,
            events=events,
            next_pos=next_pos
        )

    def on_continue(
        self,
        container: Container,
        ctx: ParsingContext
    ) -> RuleResult:
        if not isinstance(container.data, ListData):
            return RuleResult.fail()

        if ctx.cursor.indent > container.data.indent or ctx.cursor.is_eol_at(ctx.cursor.pos):
            container.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end,
            )
            return RuleResult.continue_ok()

        return RuleResult.fail()

    def on_close(
        self, 
        container: Container, 
        ctx: ParsingContext,
    ) -> RuleResult:
        assert container.closing_boundary is not None

        return RuleResult(
            status=FlowControl.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.LIST_ITEM,
                    span=ctx.cursor.new_span(
                        start=container.closing_boundary.start,
                        end=container.closing_boundary.end,
                    )
                )
            ]
        )