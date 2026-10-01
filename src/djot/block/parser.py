from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from ..input import InputText
from ..event import (
    Event,
    BlockLeaf,
    InlineLeaf,
)
from ..options import Options
from ..common import Range

from .container import (
    ParsingContext,
    Container,
    FlowControl,
    BlockRule,
    RuleResult,
)
from .state import (
    BlockState,
)

from .para import ParaRule
from .blockquote import BlockquoteRule
from .heading import HeadingRule
from .caption import CaptionRule
from .footnote import FootnoteRule
from .ref_def import ReferenceDefinitionRule
from .thematic import ThematicBreakRule
from .list import ListRule, ListItemRule
from .table import TableRule
from .attribute import AttributeRule
from .fenced import FencedDivRule
from .code_block import CodeBlockRule

@dataclass(slots=True, frozen=True)
class LineStepFrame:
    last_matched_idx: int = -1
    finished_line: bool = False
    new_starts_created: bool = False
    events: List[Event] = field(default_factory=list)

class EventParser:
    def __init__(self, src: str, options: Options | None = None) -> None:

        self.options = options or Options()

        self.state = BlockState(InputText(src))

        self.para_rule = ParaRule()
        self.block_rules: List[BlockRule] = [
            BlockquoteRule(),
            HeadingRule(),
            CaptionRule(),
            FootnoteRule(),
            ReferenceDefinitionRule(),
            ThematicBreakRule(),
            ListRule(),
            ListItemRule(),
            TableRule(options=self.options),
            AttributeRule(),
            FencedDivRule(),
            CodeBlockRule()
        ]

    def process_line(self) -> List[Event]:
        self.state.start_newline()
        events: List[Event] = []

        # 1. Check container continuation (Step 1)
        frame = self._check_continuations()
        events.extend(frame.events)
        self.state.update_last_event(events)

        #  if we hit a close fence, we can move to next line
        if frame.finished_line:
            close_events = self.state.close_container_to_depth(frame.last_matched_idx)
            events.extend(close_events)
            self.state.update_last_event(events)
            return events

        # Check for new container
        self.state.skip_space()

        frame = self._try_open_new_cotainer(
            frame.last_matched_idx
        )
        events.extend(frame.events)
        self.state.update_last_event(events)
        if frame.finished_line:
            return events

        # handle remaining content
        closure_events = self._handle_container_closures(
            last_matched_idx=frame.last_matched_idx,
            new_starts_created=frame.new_starts_created,
        )
        events.extend(closure_events)
        self.state.update_last_event(events)

        # add paragraph by default if there's text
        text_events = self._consume_line_text(
            tip=self.state.top_container,
            new_starts_created=frame.new_starts_created
        )
        events.extend(text_events)
        self.state.update_last_event(events)

        return events

    def _check_continuations(self) -> LineStepFrame:
        """Check Open Containers continuation

        The index 0 in `self.containers` represents the outmost container.
        The higher the index, the deeper an element.
        Check continuation should start from outmost to innnermost,
        as if an outer element becomes invalid, nested element
        should definitely become invalid.
        """
        last_matched_idx = -1
        line_is_finished = False
        events: List[Event] = []

        # 1. Determine if the top of curent stack has a raw block like CodeBlock.
        has_raw_barrierr = (self.state.raw_barrier_idx != -1)

        for idx, container in enumerate(self.state.container_stack):
            # 1. Prepare cursor for rule
            self.state.skip_space()

            # 2. If current container contains a raw text block,
            # flag it as is_covered, indicating that you are shadowed
            # by inner containers, yield your right to children.
            is_covered = has_raw_barrierr and (idx < self.state.raw_barrier_idx)

            res = container.on_continue(ParsingContext(
                cursor=self.state.cursor,
                is_covered=is_covered,
            ))

            # The moment a container cannot continue, stop immediately
            if res == FlowControl.CONTINUE:
                last_matched_idx = idx
                if res.events:
                    events.extend(res.events)

                if res.finished_line:
                    line_is_finished = True
                    break # If the line is processed, stop.
            else:
                break

        return LineStepFrame(
            last_matched_idx=last_matched_idx,
            finished_line=line_is_finished,
            events=events, 
        )

    def _try_open_new_cotainer(self, last_matched_idx: int) -> LineStepFrame:
        # Fast Pass Guard
        self.state.skip_space()
        if self.state.is_blank_line:
            return LineStepFrame(last_matched_idx=last_matched_idx)

        # If found last matched container, but the container does not allow
        # block type as its child, stop.
        parent = self.state.last_matched_container(last_matched_idx)
        if parent and not parent.accepts_block:
            return LineStepFrame(last_matched_idx=last_matched_idx)

        # Why finding words stops?
        if self.state.cursor.find_word():
            return LineStepFrame(last_matched_idx=last_matched_idx)

        # Cascade Open
        return self._apply_rules(parent, last_matched_idx)

    def _apply_rules(self, parent: Optional[Container], parent_idx: int) -> LineStepFrame:
        events: List[Event] = []
        last_matched_idx = parent_idx
        new_starts_created = False

        while True:
            opened_any = False

            for rule in self.block_rules:
                # Check relationship to parent element.
                if parent and not parent.can_nest(rule):
                    continue
                elif not rule.can_be_root():
                    continue

                open_res = self._try_open(rule)
                if open_res is None:
                    continue

                events.extend(open_res.events)
                last_matched_idx = len(self.state.container_stack)-1
                new_starts_created = True

                opened_any = True

                if open_res.finished_line:
                    return LineStepFrame(
                        last_matched_idx=last_matched_idx,
                        finished_line=True,
                        new_starts_created=new_starts_created,
                        events=events,
                    )

                self.state.skip_space()

                if not rule.accepts_blocks():
                    return LineStepFrame(
                        last_matched_idx=last_matched_idx,
                        new_starts_created=new_starts_created,
                        events=events,
                    )

            if not opened_any:
                break
        
        return LineStepFrame(
            last_matched_idx=last_matched_idx,
            new_starts_created=new_starts_created,
            events=events,
        )

    def _try_open(self, rule: BlockRule) -> RuleResult | None:
        result = rule.try_open(self.state.cursor)
        
        if result.status != FlowControl.OPEN:
            return None

        if result.container is None:
            raise Exception('No container created after opening an element')

        # Explicitly close sibling containers before adding current one.
        closed_events = self.state.close_siblings_of(result.container)
        
        result.events.extend(closed_events)

        result.container = self.state.push_container(
            result.container,
            self.options
        )
        return result

    def _handle_container_closures(
        self,
        last_matched_idx: int,
        new_starts_created: bool
    ) -> List[Event]:
        """
        Check if the following content is lazy.
        """
        events: List[Event] = []
        tip = self.state.top_container

        # 判定是否为 Lazy Paragraph Continuation
        is_lazy = (
            not self.state.is_blank_line
            and not new_starts_created
            and last_matched_idx < len(self.state.container_stack) - 1 # not last one
            and tip is not None
            and tip.rule.accepts_inline_only()
        )

        if not is_lazy:
            # Stack might change here.
            # Therefore djot.js perform tip = self.tip() again after here.
            events.extend(self.state.close_container_to_depth(last_matched_idx))

        return events

    def _consume_line_text(
        self,
        tip: Optional[Container],
        new_starts_created: bool,
    ) -> List[Event]:
        events = []
        is_blank = self.state.is_blank_line

        if tip is None or tip.rule.accepts_block_only():
            if is_blank:
                if not new_starts_created:
                    # need to track these for tight/loose lists.
                    events.append(
                        Event.leaf(
                            kind=BlockLeaf.BLANKLINE,
                            span=self.state.cursor.rest_line_span()
                        )
                    )
                return events
            else:
                # In djot.js, open paragraph adds a new container and event.
                open_result = self.para_rule.try_open(self.state.cursor)
                # ParaRule could always open a new container.
                assert open_result.container is not None

                closed_events = self.state.close_siblings_of(open_result.container)
                events.extend(closed_events)
                
                para_container = self.state.push_container(open_result.container, self.options)
                events.extend(open_result.events)

                tip = para_container

        if tip.rule.accepts_text_only(): # if child node is text only.
            start_pos = self.state.get_adjusted_text_start(tip.indent)
            events.append(
                Event.leaf(
                    kind=InlineLeaf.STR,
                    span=self.state.cursor.new_span(start_pos, self.state.cursor.eol_start)
                )
            ) # gobble the whole line.
        elif tip.rule.accepts_inline_only and not is_blank: # if child nodes are inline elements.
            if tip.inline_parser: # guard inline parse is set.
                tip.inline_parser.feed(
                    self.state.cursor.pos,
                    self.state.cursor.eol_end
                )

        return events

    def parse(self) -> Iterator[Event]:
        while not self.state.cursor.is_eof():
            line_events = self.process_line()

            for event in line_events:
                yield event

            self.state.cursor.advance_to_new_line()


        for event in self.state.close_container_to_depth(-1):
            yield event

