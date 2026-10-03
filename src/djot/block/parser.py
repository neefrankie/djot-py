from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from ..input import InputText
from ..event import (
    Event,
    BlockLeaf,
    InlineLeaf,
)
from ..options import Options
from ..logger import logger

from .container import (
    ParsingContext,
    Container,

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

    def __repr__(self) -> str:
        return f'LineStepFrame(last_matched_idx={self.last_matched_idx}, finished_line={self.finished_line}, new_starts_created={self.new_starts_created}, events[{len(self.events)}])'

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
        logger.debug(f'\n▶ Start a newline: {self.state.cursor} ===')
        events: List[Event] = []

        logger.debug(f'--- Stage: check continuation ---')
        # 1. Check container continuation (Step 1)
        frame = self._check_continuations()
        logger.debug(f'Frame after continuation: {frame}')

        events.extend(frame.events)
        self.state.update_last_event(events)

        #  if we hit a close fence, we can move to next line
        if frame.finished_line:
            logger.debug(f'--- Finished a line due to continuation')
            close_events = self.state.close_container_to_depth(frame.last_matched_idx)
            events.extend(close_events)
            self.state.update_last_event(events)
            return events

        logger.debug(f'--- Stage: try open ----')
        # Check for new container
        frame = self._try_open_new_cotainer(
            frame.last_matched_idx
        )
        logger.debug(f'Frame after exhausting opening rules: {frame}')

        events.extend(frame.events)
        self.state.update_last_event(events)
        # Stop if the whole line is eaten.
        if frame.finished_line:
            logger.debug(f'--- Finished a line due to open')
            return events

        logger.debug(f'--- Stage: close containers ---')
        # handle remaining content
        closure_events = self._handle_container_closures(
            last_matched_idx=frame.last_matched_idx,
            new_starts_created=frame.new_starts_created,
        )
        events.extend(closure_events)
        self.state.update_last_event(events)

        logger.debug(f'--- Stage: consume rest line ---')
        # add paragraph by default if there's text
        text_events = self._consume_line_text(
            tip=self.state.top_container,
            new_starts_created=frame.new_starts_created
        )
        events.extend(text_events)
        self.state.update_last_event(events)

        logger.debug('--- Finished processing a line ---')
        return events

    def _check_continuations(self) -> LineStepFrame:
        """Check Open Containers continuation

        The index 0 in `self.containers` represents the outmost container.
        The higher the index, the deeper an element.
        Check continuation should start from outmost to innnermost,
        as if an outer element becomes invalid, nested element
        should definitely become invalid.

        NOTE:
        djot.js makes implicit assumption that any continue method will
        either move the cursor to EOL, or does not move it any all.
        """
        logger.debug(f'{self.state.cursor.pos}. Check continuation stack {len(self.state.container_stack)}')

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
            logger.debug(f'{self.state.cursor.pos}. {container} continue result: {res}')

            if res.finished_line:
                line_is_finished = True

            # The moment a container cannot continue, stop immediately
            if res.is_continue:
                last_matched_idx = idx
                if res.events:
                    events.extend(res.events)
            else:
                break

            # NOTE: res.finished_line is not bound to res.status.
            # Be very careful. Djot.js heavily relies on this unpredicated state.
            if line_is_finished:
                break

        return LineStepFrame(
            last_matched_idx=last_matched_idx,
            finished_line=line_is_finished,
            events=events, 
        )

    def _try_open_new_cotainer(self, last_matched_idx: int) -> LineStepFrame:
        logger.debug(f'{self.state.cursor.pos} --- Try open new containers')
        self.state.skip_space()

        # In djot.js, it uses let isBlank = (self.pos === self.starteol);
        # However, the logic here is not actually ask if the line is blank.
        # It is asking if the rest of line is blank, or Residual Blank Line
        if self.state.cursor.is_eof:
            logger.debug(f'{self.state.cursor.pos}. Current cursor has moved to EOL after skipping leading space. Stop trying to open any container.')
            return LineStepFrame(last_matched_idx=last_matched_idx)

        # If found last matched container, but the container does not allow
        # block type as its child, stop.
        parent = self.state.last_matched_container(last_matched_idx)
        if parent and not parent.accepts_block:
            logger.debug(f'Parent container {parent} does not acceppt block element. Stop trying to open any container.')
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

            logger.debug(f'{self.state.cursor.pos} --- Start trying rule')

            for rule in self.block_rules:
                logger.debug(f'{self.state.cursor.pos}. 📣 Try new rule {rule.__class__.__name__}')
                # Check relationship to parent element.
                is_type_matched = (
                    rule.can_be_root()
                    if parent is None
                    else parent.can_nest(rule)
                )
                if not is_type_matched:
                    continue

                open_res = self._try_open(rule, last_matched_idx)
                if open_res is None:
                    logger.debug(f'{self.state.cursor.pos}. {rule.__class__.__name__} cannot open')
                    continue

                logger.debug(f'{self.state.cursor.pos}. 🌈 {rule.__class__.__name__} open result {open_res}')

                events.extend(open_res.events)
                last_matched_idx = len(self.state.container_stack)-1
                parent = self.state.container_stack[last_matched_idx] # move node in tree deeper

                logger.debug(f'{self.state.cursor.pos}. Update last matched container to {last_matched_idx}')

                if open_res.finished_line:
                    logger.debug(f'{rule.__class__.__name__} finished a line')
                    return LineStepFrame(
                        last_matched_idx=last_matched_idx,
                        finished_line=True,
                        new_starts_created=new_starts_created,
                        events=events,
                    )

                self.state.skip_space()

                new_starts_created = True

                opened_any = True

                # Check if current rule could nest a child block.
                if not rule.accepts_blocks():
                    return LineStepFrame(
                        last_matched_idx=last_matched_idx,
                        new_starts_created=new_starts_created,
                        events=events,
                    )

            logger.debug(f'{self.state.cursor.pos}. Exhausted all rules. Opened any: {opened_any}')
            if not opened_any:
                break
        
        return LineStepFrame(
            last_matched_idx=last_matched_idx,
            new_starts_created=new_starts_created,
            events=events,
        )

    def _try_open(self, rule: BlockRule, last_matched_idx: int) -> RuleResult | None:
        result = rule.try_open(self.state.cursor)
        
        if not result.is_open:
            return None

        if result.container is None:
            raise Exception('No container created after opening an element')

        logger.debug(f'{self.state.cursor.pos}. ✅{rule.__class__.__name__} opened')

        closed_events = self.state.close_containers(last_matched_idx, result.container)

        result.events = closed_events + result.events

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
        self.state.skip_space()
        is_eol = self.state.cursor.is_eol

        tip = self.state.top_container

        # Lazy Paragraph Continuation
        is_lazy = (
            not is_eol
            and not new_starts_created
            and last_matched_idx < len(self.state.container_stack) - 1 # not last one
            and tip is not None
            and tip.rule.accepts_inline_only()
        )

        if not is_lazy:
            logger.debug(f'{self.state.cursor.pos}. Not lazy content. Close containers to {last_matched_idx}.')
            # Stack might change here.
            # Therefore djot.js perform tip = self.tip() again after here.
            return self.state.close_container_to_depth(last_matched_idx)

        return []

    def _consume_line_text(
        self,
        tip: Optional[Container],
        new_starts_created: bool,
    ) -> List[Event]:
        self.state.cursor.skip_space()
        events = []
        is_eol = self.state.cursor.is_eol

        if tip is None or tip.rule.accepts_block_only(): # For example blockquote
            if is_eol:
                if not new_starts_created:
                    logger.debug(f'{self.state.cursor.pos}. Create blankline')
                    # need to track these for tight/loose lists.
                    # NOTE: what is considered as a blackline?
                    # An empty line, of course. Anything else?
                    # A blockquote line with '>' symbol only.
                    # The blanklin defined in markdown/djot is different
                    # from physical blankline.
                    pos = self.state.cursor.pos
                    line_end = self.state.cursor.eol_end
                    events.append(
                        Event.leaf(
                            kind=BlockLeaf.BLANKLINE,
                            span=self.state.cursor.new_span(pos, line_end)
                        )
                    )
                return events
            else:
                logger.debug(f'{self.state.cursor.pos}. Fallback to paragraph.')
                # In djot.js, open paragraph adds a new container and event.
                open_result = self.para_rule.try_open(self.state.cursor)
                # ParaRule could always open a new container.
                assert open_result.container is not None

                closed_events = self.state.close_siblings_of(open_result.container)
                events.extend(closed_events)
                
                para_container = self.state.push_container(open_result.container, self.options)
                events.extend(open_result.events)

                tip = para_container

        if tip.rule.accepts_text_only(): # if child node is text only. Clode block.
            start_pos = self.state.get_adjusted_text_start(tip.indent)
            logger.debug(f'{self.state.cursor.pos}. Text only.')
            events.append(
                Event.leaf(
                    kind=InlineLeaf.STR,
                    span=self.state.cursor.new_span(start_pos, self.state.cursor.eol_start)
                )
            ) # gobble the whole line.
        elif tip.rule.accepts_inline_only and not is_eol: # if child nodes are inline elements.
            if tip.inline_parser: # guard inline parse is set.
                logger.debug(f'{self.state.cursor.pos}. Parse inline content to {self.state.cursor.eol_end}')
                tip.inline_parser.feed(
                    self.state.cursor.pos,
                    self.state.cursor.eol_end
                )

        return events

    def parse(self) -> Iterator[Event]:
        while not self.state.cursor.is_eof:
            line_events = self.process_line()

            for event in line_events:
                yield event

            self.state.cursor.advance_to_new_line()

        logger.debug(f'{self.state.cursor.pos}. Cleanup.')
        for event in self.state.close_container_to_depth(-1):
            yield event

