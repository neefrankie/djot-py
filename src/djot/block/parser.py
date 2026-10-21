from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from ..input import InputText
from ..event import (
    Event,
    BlockLeaf,
    InlineLeaf,
)
from ..logger import logger

from .container import (
    ParsingContext,
    BlockFrame,
    OpenStatus,
    BlockRule,
    OpenResult,
    LineAction,
    ContinueAction,
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
    def __init__(self, src: str) -> None:

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
            TableRule(),
            AttributeRule(),
            FencedDivRule(),
            CodeBlockRule()
        ]

    @property
    def source_text(self) -> str:
        return self.state.cursor.src
    
    def process_line(self) -> List[Event]:
        
        logger.debug(f'▶ Start a newline: {self.state.cursor} ===')
        events: List[Event] = []

        logger.debug(f'--- Stage: check continuation ---')
        # 1. Check container continuation (Step 1)
        frame = self._check_continuations()
        logger.debug(f'Frame after continuation: {frame}')

        events.extend(frame.events)

        #  if we hit a close fence, we can move to next line
        if frame.finished_line:
            logger.debug(f'--- Finished a line due to continuation')
            return events

        logger.debug(f'--- Stage: try open ----')
        # Check for new container
        frame = self._try_open_new_frame(
            frame.last_matched_idx
        )
        logger.debug(f'Frame after exhausting opening rules: {frame}')

        events.extend(frame.events)
        
        # Stop if the whole line is eaten.
        if frame.finished_line:
            logger.debug(f'--- Finished a line due to open')
            return events

        logger.debug(f'--- Stage: handle lazy content ---')
        close_events = self._close_unmatched_if_not_lazy(
            last_matched_idx=frame.last_matched_idx,
            new_starts_created=frame.new_starts_created
        )

        events.extend(close_events)

        logger.debug(f'--- Stage: consume rest line ---')
        # add paragraph by default if there's text
        text_events = self._consume_line_text(
            tip=self.state.top_frame,
            last_matched_idx=frame.last_matched_idx,
            new_starts_created=frame.new_starts_created
        )
        events.extend(text_events)

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
        logger.debug(f'{self.state.cursor.pos}. Start checking continuation stack {len(self.state.frame_stack)}')

        last_matched_idx = -1
        line_is_finished = False
        is_explicit_close = False # True indicates explicitly closed element appeared.
        events: List[Event] = []

        # 1. Determine if the top of curent stack has a raw block like CodeBlock.
        has_raw_barrierr = (self.state.raw_barrier_idx != -1)

        for idx, frame in enumerate(self.state.frame_stack):
            
            # 1. Prepare cursor for rule
            self.state.cursor.skip_frame_space()

            # 2. If current container contains a raw text block,
            # flag it as is_covered, indicating that you are shadowed
            # by inner containers, yield your right to children.
            is_covered = has_raw_barrierr and (idx < self.state.raw_barrier_idx)

            cont_res = frame.on_continue(ParsingContext(
                cursor=self.state.cursor,
                is_covered=is_covered,
            ))

            logger.debug(f'{self.state.cursor.pos}. {frame} continue result: {cont_res}')

            if cont_res.next_pos is not None:
                logger.debug(f'Cursor is moving from {self.state.cursor.pos} to {cont_res.next_pos}')
                self.state.cursor.advance_pos(cont_res.next_pos)

            if cont_res.line_action == LineAction.CONSUMED:
                line_is_finished = True

            events.extend(cont_res.events)

            match cont_res.action:
                case ContinueAction.STOP:
                    break

                case ContinueAction.CLOSE:
                    is_explicit_close = True
                    break

                case ContinueAction.CONTINUE:
                    last_matched_idx = idx


        if is_explicit_close:
            close_events = self.state.close_frame_to_depth(last_matched_idx)
            # Ensure proper order since continued events
            # should not come before previous elements' closed events.
            events = close_events + events

        return LineStepFrame(
            last_matched_idx=last_matched_idx,
            finished_line=line_is_finished,
            events=events, 
        )

    def _try_open_new_frame(self, last_matched_idx: int) -> LineStepFrame:
        logger.debug(f'{self.state.cursor.pos} --- Try open new containers')
        self.state.cursor.skip_frame_space()

        # In djot.js, it uses let isBlank = (self.pos === self.starteol);
        # However, the logic here is not actually ask if the line is blank.
        # It is asking if the rest of line is blank, or Residual Blank Line
        if self.state.cursor.is_eol_reached:
            logger.debug(f'{self.state.cursor.pos}. Current cursor has moved to EOL after skipping leading space. Stop trying to open any container.')
            return LineStepFrame(last_matched_idx=last_matched_idx)

        # If found last matched container, but the container does not allow
        # block type as its child, stop.
        parent = self.state.last_matched_container(last_matched_idx)
        if parent and not parent.accepts_block:
            logger.debug(f'Parent container {parent} does not acceppt block element. Stop trying to open any container.')
            return LineStepFrame(last_matched_idx=last_matched_idx)

        # Why finding words stops?
        if self.state.cursor.is_word(self.state.cursor.pos):
            return LineStepFrame(last_matched_idx=last_matched_idx)

        # Cascade Open
        return self._apply_rules(parent, last_matched_idx)

    def _apply_rules(self, parent: Optional[BlockFrame], parent_idx: int) -> LineStepFrame:
        events: List[Event] = []
        last_matched_idx = parent_idx
        # Based on its used, this variable cover two meanings:
        # 1. did open a new container
        # 2. current line is not consumed by this container.
        # However, when it was used, current line is always not 
        # consumed to the end as finished_line = true short circuit to next line.
        new_starts_created = False

        # The while loop determines the type of an element after each advancement.
        # When should you break out of the while loop?
        # 1. If no rule applied.
        # 2. If a rule matched, but does not accept further block elements.
        # 3. If a rule matches, and consumed the whole line.
        # 4. Fallback
        while True:
            more_frames_required = False

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

                result = rule.try_open(self.state.cursor)

                match result.status:
                    case OpenStatus.NOT_MATCHED:
                        logger.debug(f'{self.state.cursor.pos}. {rule.__class__.__name__} cannot open')
                        continue

                    case OpenStatus.FALLBACK:
                        logger.debug(f'{self.state.cursor.pos}. {rule.__class__.__name__} fallback.')
                        _, para_events = self._open_para(last_matched_idx)

                        last_matched_idx = self.state.last_frame_index
                        events.extend(para_events)

                        return LineStepFrame(
                            last_matched_idx=last_matched_idx,
                            events=events,
                        )

                    case OpenStatus.MATCHED:
                        logger.debug(f'{self.state.cursor.pos}. {rule.__class__.__name__} matched.')

                        events.extend(self._handle_matched(last_matched_idx, result))
                        if result.frame is not None:
                            last_matched_idx = self.state.last_frame_index
                            parent = self.state.frame_stack[last_matched_idx]

                        self.state.cursor.skip_frame_space()

                        if rule.accepts_blocks():
                            more_frames_required = True
                            break
                        else:
                            return LineStepFrame(
                                last_matched_idx=last_matched_idx,
                                new_starts_created=new_starts_created,
                                events=events,
                            )

                    case OpenStatus.MATCH_AND_CONSUMED:
                        events.extend(self._handle_matched(last_matched_idx, result))

                        if result.frame is not None:
                            last_matched_idx = self.state.last_frame_index
                        return LineStepFrame(
                            last_matched_idx=last_matched_idx,
                            finished_line=True,
                            new_starts_created=new_starts_created,
                            events=events,
                        )

            logger.debug(f'{self.state.cursor.pos}. Exhausted all rules.')

            if not more_frames_required:
                logger.debug(f'{self.state.cursor.pos}. No rule applicable. Fallthrough.')
                break
        
        return LineStepFrame(
            last_matched_idx=last_matched_idx,
            new_starts_created=new_starts_created,
            events=events,
        )

    def _handle_matched(
        self, 
        last_matched_idx: int,
        result: OpenResult
    ):
        events = self.state.close_frame_to_depth(
            last_matched_idx,
        )

        if result.frame is not None:
            sibling_events = self.state.close_frame_to_parent(
                result.frame,
            )
            events.extend(sibling_events)
            self.state.push_frame(result.frame)

        events.extend(result.events)

        return events

    def _close_unmatched_if_not_lazy(
        self,
        last_matched_idx: int,
        new_starts_created: bool,
    ) -> List[Event]:
        """
        Check if the following content is lazy.
        For example,

        > Blockquote paragraph
        Paragraph continnued.
        """
        self.state.cursor.skip_frame_space()

        is_eol = self.state.cursor.is_eol_reached
        
        tip = self.state.top_frame

        is_lazy = (
            not is_eol
            and not new_starts_created # If we created a new container, and the container has trailing content, do not trigger lazy continuation
            and last_matched_idx < len(self.state.frame_stack) - 1 # not last one
            and tip is not None
            and tip.rule.accepts_inline_only() # paraggraph, heading, caption
        )

        if not is_lazy:
            logger.debug(f'{self.state.cursor.pos}. Not lazy content. Close frames to {last_matched_idx}.')
            
            events = self.state.close_frame_to_depth(last_matched_idx)

            return events

        return []

    def _open_para(self, last_matched_idx: int):
        logger.debug(f'{self.state.cursor.pos}. Fallback to paragraph.')
        
        result = self.para_rule.try_open(self.state.cursor)
        # ParaRule could always open a new container.
        assert result.frame is not None

        logger.debug(f'{self.state.cursor.pos}. ✅Para opened')

        closed_events = self.state.close_frames(last_matched_idx, result.frame)

        events = closed_events + result.events
        
        frame = self.state.push_frame(
            result.frame,
        )

        return (frame, events)

    def _parse_inline(self, tip: BlockFrame):
        """Parse inline content for paragraph, heading and caption.

        When they are in lazy mode, they escaped the on_continue check.
        This is tricky since we rely on on_continue to update
        this container's closing position.
        """
        if tip.inline_parser: # guard inline parse is set.
            logger.debug(f'{self.state.cursor.pos}. Parse inline content to {self.state.cursor.line_end}')
            tip.inline_parser.feed(
                self.state.cursor.pos,
                self.state.cursor.line_end
            )
            line_end = self.state.cursor.line_end
            tip.update_closing_boundary(line_end, line_end) # TODO: a temporary solution for lazy content

    def _parse_text(self, tip: BlockFrame) -> Event:
        """Code block"""
        start_pos = self.state.get_adjusted_text_start(tip.indent)
        logger.debug(f'{self.state.cursor.pos}. Text only.')
        event = Event.leaf(
            kind=InlineLeaf.STR,
            span=self.state.cursor.new_span(start_pos, self.state.cursor.line_end)
        ) # gobble the whole line.
        # tip.last_eol = self.state.cursor.eol_end

        return event

    def _parse_blankline(self, tip: BlockFrame | None) -> Event:
        line_end = self.state.cursor.line_end

        if tip and tip.closing_boundary:
            logger.debug(f'{self.state.cursor.pos}. parse bankline: {tip} updates last closing boundary to {line_end}')
            tip.update_closing_boundary(line_end, line_end)
        
        return Event.leaf(
            kind=BlockLeaf.BLANKLINE,
            span=self.state.cursor.new_span(line_end, line_end)
        )
        

    def _is_lazy_line(
        self,
        last_matched_idx: int,
        new_starts_created: bool
    ) -> bool:
        """
        Check if the following content is lazy.
        For example,

        > Blockquote paragraph
        Paragraph continnued.
        """
        self.state.cursor.skip_frame_space()
        is_eol = self.state.cursor.is_eol_reached
        
        tip = self.state.top_frame

        return (
            not is_eol
            and not new_starts_created
            and last_matched_idx < len(self.state.frame_stack) - 1 # not last one
            and tip is not None
            and tip.rule.accepts_inline_only() # paraggraph, heading, caption
        )

    def _consume_line_text(
        self,
        tip: Optional[BlockFrame],
        last_matched_idx: int,
        new_starts_created: bool,
    ) -> List[Event]:
        """
        If there are still contents after exhausted continue container and open container.
        """
        self.state.cursor.skip_frame_space()
        events = []
        is_eol = self.state.cursor.is_eol_reached

        if tip is None or tip.rule.accepts_block_only(): # For example blockquote
            if is_eol:
                if not new_starts_created:
                    logger.debug(f'{self.state.cursor.pos}. Create blankline')
                    # need to track these for tight/loose lists.
                    # NOTE: what is considered as a blankline?
                    # An empty line, of course. Anything else?
                    # A blockquote line with '>' symbol only.
                    # The blanklin defined in markdown/djot is different
                    # from physical blankline.
                    event = self._parse_blankline(tip)
                    events.append(event)
                return events
            else:
                tip, opened_events = self._open_para(last_matched_idx)
                events.extend(opened_events)

        if tip.rule.accepts_text_only(): # if child node is text only. Clode block.
            events.append(self._parse_text(tip)) # gobble the whole line.
        elif tip.rule.accepts_inline_only and not is_eol: # if child nodes are inline elements.
            self._parse_inline(tip)

        return events

    def parse(self) -> Iterator[Event]:
        while self.state.cursor.next_line():
            line_events = self.process_line()

            for event in line_events:
                yield event

        logger.debug(f'{self.state.cursor.pos}. Cleanup.')
        for event in self.state.close_frame_to_depth(-1):
            yield event

