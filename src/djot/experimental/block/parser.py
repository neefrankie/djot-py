from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from djot.event import (
    Event,
    BlockLeaf,
    InlineLeaf,
)
from djot.logger import logger

from ..cursor import (
    LineContext,
    Cursor,
)

from .frame import (
    ParsingContext,
    BlockFrame,
    BlockRule,
    RuleResult,
)
from .state import (
    BlockState,
)

from .attribute import AttributeRule
from .para import ParaRule


@dataclass(slots=True, frozen=True)
class LineStepFrame:
    line: LineContext
    last_matched_idx: int = -1
    finished_line: bool = False
    new_starts_created: bool = False
    events: List[Event] = field(default_factory=list)

    def __repr__(self) -> str:
        return f'LineStepFrame(line={self.line}, last_matched_idx={self.last_matched_idx}, finished_line={self.finished_line}, new_starts_created={self.new_starts_created}, events[{len(self.events)}])'

class EventParser:
    def __init__(self, src: str) -> None:

        self.state = BlockState(
            cursor=Cursor(src)
        )

        self.para_rule = ParaRule()
        self.block_rules: List[BlockRule] = [
            AttributeRule(),
        ]

    @property
    def source_text(self) -> str:
        return self.state.cursor.src
    
    def process_line(self, line: LineContext) -> List[Event]:
        logger.debug(f'▶ Processing a newline: {line.pos}')
        events: List[Event] = []

        logger.debug(f'--- Stage: check continuation ---')
        # 1. Check container continuation (Step 1)
        frame = self._check_continuations(line)
        logger.debug(f'Frame after continuation: {frame}')

        events.extend(frame.events)

        #  if we hit a close fence, we can move to next line
        if frame.finished_line:
            logger.debug(f'Finished a line due to continuation')
            close_events = self.state.close_frame_to_depth(
                frame.last_matched_idx,
                frame.line,
            )
            events.extend(close_events)
            return events

        line = frame.line

        logger.debug(f'--- Stage: try open ----')
        # Check for new container
        frame = self._try_open_new_cotainer(
            frame.last_matched_idx,
            line,
        )
        logger.debug(f'Frame after exhausting opening rules: {frame}')

        events.extend(frame.events)
        
        # Stop if the whole line is eaten.
        if frame.finished_line:
            logger.debug(f'--- Finished a line due to open')
            return events

        logger.debug(f'--- Stage: handle lazy content ---')

        line = self.state.cursor.skip_frame_space(line)
        is_lazy = self._is_lazy_line(
            last_matched_idx=frame.last_matched_idx,
            new_starts_created=frame.new_starts_created,
            line=line,
        )

        logger.debug(f'{line.pos}. Is lazy content: {is_lazy}')

        if not is_lazy:
            logger.debug(f'{line.pos}. Not lazy content. Close containers to {frame.last_matched_idx}.')
            # Stack might change here.
            # Therefore djot.js perform tip = self.tip() again after here.
            events.extend(
                self.state.close_frame_to_depth(
                    frame.last_matched_idx,
                    line,
                )
            )


        logger.debug(f'--- Stage: consume rest line ---')
        # add paragraph by default if there's text
        text_events = self._consume_line_text(
            frame=self.state.top_frame,
            last_matched_idx=frame.last_matched_idx,
            new_starts_created=frame.new_starts_created,
            line=line,
        )
        events.extend(text_events)

        logger.debug('--- Finished processing a line ---')
        return events

    def _check_continuations(self, line: LineContext) -> LineStepFrame:
        """Check Open Containers continuation

        The index 0 in `self.containers` represents the outmost container.
        The higher the index, the deeper an element.
        Check continuation should start from outmost to innnermost,
        because if an outer element becomes invalid, nested element
        should definitely become invalid.
        """
        logger.debug(f'{line.pos}. Start checking continuation stack {len(self.state.frame_stack)}')

        last_frame_idx = -1
        line_is_finished = False
        events: List[Event] = []

        # 1. Determine if the top of curent stack has a raw block like CodeBlock.
        has_raw_barrierr = (self.state.raw_barrier_idx != -1)

        for idx, frame in enumerate(self.state.frame_stack):
            
            # Skip leading spaces of current frame and 
            # go to the first non-space char.
            # This is NOT skipping leading space of a line.
            line = self.state.cursor.skip_frame_space(line)

            # 2. If current container contains a raw text block,
            # flag it as is_covered, indicating that you are shadowed
            # by inner containers, yield your right to children.
            is_covered = has_raw_barrierr and (idx < self.state.raw_barrier_idx)

            res = frame.on_continue(ParsingContext(
                cursor=self.state.cursor,
                line=line,
                is_covered=is_covered,
            ))
            logger.debug(f'{frame} continue result: {res}')
            if res.next_pos is not None:
                logger.debug(f'Cursor is moving from {line.pos} to {res.next_pos.pos}')

            # TODO: replace this by next_pos == cursor.eol_end?
            if res.finished_line:
                line_is_finished = True

            # The moment a container cannot continue, stop immediately
            if res.is_continue:
                last_frame_idx = idx
                if res.events:
                    events.extend(res.events)
            else:
                # LINE_FINIFHSHED will also break
                break

        return LineStepFrame(
            line=line,
            last_matched_idx=last_frame_idx,
            finished_line=line_is_finished,
            events=events, 
        )

    def _try_open_new_cotainer(
            self,
            last_matched_idx: int,
            line: LineContext,
    ) -> LineStepFrame:
        logger.debug(f'{line.pos}. Try open new frame.')
        line = self.state.cursor.skip_frame_space(line)

        # In djot.js, it uses let isBlank = (self.pos === self.starteol);
        # However, the logic here is not actually ask if the line is blank.
        # It is asking if the rest of line is blank, or Residual Blank Line
        if line.is_reaching_end:
            logger.debug(f'{line.pos}. Current cursor has moved to EOL after skipping leading space. Stop trying to open any container.')
            return LineStepFrame(
                line=line,
                last_matched_idx=last_matched_idx
            )

        # If found last matched container, but the container does not allow
        # block type as its child, stop.
        parent = self.state.last_matched_frame(last_matched_idx)
        if parent and not parent.accepts_block:
            logger.debug(f'Parent container {parent} does not acceppt block element. Stop trying to open any container.')
            return LineStepFrame(
                line=line,
                last_matched_idx=last_matched_idx
            )

        # Why finding words stops?
        if self.state.cursor.is_word(line.pos):
            return LineStepFrame(
                line=line,
                last_matched_idx=last_matched_idx
            )

        # Cascade Open
        return self._apply_rules(
            parent,
            last_matched_idx,
            line
        )

    def _apply_rules(
        self,
        parent: Optional[BlockFrame],
        parent_idx: int,
        line: LineContext,
    ) -> LineStepFrame:
        events: List[Event] = []
        last_matched_idx = parent_idx
        new_starts_created = False

        while True:
            opened_any = False

            logger.debug(f'{line.pos} --- Start trying rule')

            for rule in self.block_rules:
                logger.debug(f'{line.pos}. 📣 Try new rule {rule.__class__.__name__}')
                # Check relationship to parent element.
                is_type_matched = (
                    rule.can_be_root()
                    if parent is None
                    else parent.can_nest(rule)
                )
                if not is_type_matched:
                    continue

                open_res = self._try_open(rule, last_matched_idx, line)
                if open_res is None:
                    logger.debug(f'{line.pos}. {rule.__class__.__name__} cannot open')
                    continue

                if open_res.next_pos is not None:
                    logger.debug(f'Cursor moved from {line.pos} to {open_res.next_pos.pos}')
                    line = open_res.next_pos

                logger.debug(f'{line.pos}. 🌈 {rule.__class__.__name__} open result {open_res}')

                events.extend(open_res.events)
                last_matched_idx = len(self.state.frame_stack)-1
                parent = self.state.frame_stack[last_matched_idx] # move node in tree deeper

                logger.debug(f'{line.pos}. Update last matched container to {last_matched_idx}')

                if open_res.finished_line:
                    logger.debug(f'{rule.__class__.__name__} finished a line')
                    return LineStepFrame(
                        line=line,
                        last_matched_idx=last_matched_idx,
                        finished_line=True,
                        new_starts_created=new_starts_created,
                        events=events,
                    )

                self.state.cursor.skip_frame_space(line)

                new_starts_created = True

                opened_any = True

                # Check if current rule could nest a child block.
                if not rule.accepts_blocks():
                    return LineStepFrame(
                        line=line,
                        last_matched_idx=last_matched_idx,
                        new_starts_created=new_starts_created,
                        events=events,
                    )

            logger.debug(f'{line.pos}. Exhausted all rules. Opened any: {opened_any}')
            if not opened_any:
                break
        
        return LineStepFrame(
            line=line,
            last_matched_idx=last_matched_idx,
            new_starts_created=new_starts_created,
            events=events,
        )

    def _try_open(
        self, 
        rule: BlockRule, 
        last_matched_idx: int,
        line: LineContext,
    ) -> RuleResult | None:
        result = rule.try_open(ParsingContext(
            cursor=self.state.cursor,
            line=line,
        ))
        
        if not result.is_open:
            return None

        if result.frame is None:
            raise Exception('No frame created after opening an element')

        closed_events = self.state.close_frames(last_matched_idx, result.frame, line)

        result.events = closed_events + result.events

        result.frame = self.state.push_frame(
            result.frame,
        )

        logger.debug(f'{line.pos}. ✅{rule.__class__.__name__} opened')
            

        return result

    def _open_para(self, last_matched_idx: int, line: LineContext) -> RuleResult:
        logger.debug(f'{line.pos}. Fallback to paragraph.')
        
        result = self.para_rule.try_open(ParsingContext(
            cursor=self.state.cursor,
            line=line,
        ))
        # ParaRule could always open a new container.
        assert result.frame is not None

        logger.debug(f'{line.pos}. ✅Para opened')

        closed_events = self.state.close_frames(
            last_matched_idx,
            result.frame,
            line
        )

        result.events = closed_events + result.events
        
        result.frame = self.state.push_frame(
            result.frame,
        )

        if result.next_pos is not None:
            logger.debug(f'Cursor is moving from {line.pos} to {result.next_pos.pos}')
            line = result.next_pos

        return result

    def _parse_inline(self, tip: BlockFrame, line: LineContext):
        """Parse inline content for paragraph, heading and caption.

        When they are in lazy mode, they escaped the on_continue check.
        This is tricky since we rely on on_continue to update
        this container's closing position.
        """
        if tip.inline_parser: # guard inline parse is set.
            logger.debug(f'{line.pos}. Parse inline content to {line.end_offset}')
            tip.inline_parser.feed(
                line.pos,
                line.end_offset,
            )
            tip.update_closing_boundary(line.end_offset, line.end_offset)

    def _parse_text(self, tip: BlockFrame, line: LineContext) -> Event:
        """Code block"""
        adjusted_line = line.adjust_indented_start(tip.indent)
        logger.debug(f'{line.pos}. Text only.')
        event = Event.leaf(
            kind=InlineLeaf.STR,
            span=self.state.cursor.new_span(adjusted_line.pos, line.end_offset)
        ) # gobble the whole line.
        # tip.last_eol = self.state.cursor.eol_end

        return event

    def _parse_blankline(self, line: LineContext, tip: BlockFrame | None) -> Event:
        line_end = line.end_offset

        if tip and tip.closing_boundary:
            logger.debug(f'{line.pos}. parse bankline: {tip} updates last closing boundary to {line_end}')
            tip.update_closing_boundary(line_end, line_end)
        
        return Event.leaf(
            kind=BlockLeaf.BLANKLINE,
            span=self.state.cursor.new_span(line_end, line_end)
        )
        

    def _is_lazy_line(
        self,
        last_matched_idx: int,
        new_starts_created: bool,
        line: LineContext,
    ) -> bool:
        """
        Check if the following content is lazy.
        For example,

        > Blockquote paragraph
        Paragraph continnued.
        """
        
        is_eol = line.is_reaching_end
        
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
        frame: Optional[BlockFrame],
        last_matched_idx: int,
        new_starts_created: bool,
        line: LineContext,
    ) -> List[Event]:
        """
        If there are still contents after exhausted continue container and open container.
        """
        line = self.state.cursor.skip_frame_space(line)
        events = []
        is_eol = line.is_reaching_end

        if frame is None or frame.rule.accepts_block_only(): # For example blockquote
            if is_eol:
                if not new_starts_created:
                    logger.debug(f'{line.pos}. Create blankline')
                    # need to track these for tight/loose lists.
                    # NOTE: what is considered as a blankline?
                    # An empty line, of course. Anything else?
                    # A blockquote line with '>' symbol only.
                    # The blanklin defined in markdown/djot is different
                    # from physical blankline.
                    event = self._parse_blankline(line, frame)
                    events.append(event)
                return events
            else:
                open_res = self._open_para(last_matched_idx, line)
                events.extend(open_res.events)
                frame = open_res.frame
                if open_res.next_pos is not None:
                    line= open_res.next_pos

        assert frame is not None

        if frame.rule.accepts_text_only(): # if child node is text only. Clode block.
            events.append(self._parse_text(frame, line)) # gobble the whole line.
        elif frame.rule.accepts_inline_only and not is_eol: # if child nodes are inline elements.
            self._parse_inline(frame, line)

        return events

    def parse(self) -> Iterator[Event]:
        next_line = self.state.cursor.next_line(LineContext())

        while next_line is not None:
            line_events = self.process_line(next_line)

            for event in line_events:
                yield event

            next_line = self.state.cursor.next_line(next_line)

        logger.debug(f'Cleanup.')
        for event in self.state.close_frame_to_depth(-1, next_line):
            yield event

