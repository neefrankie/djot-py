from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple

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
    BlockFrame,
    BlockRule,
    OpenResult,
    OpenStatus,
    ContinueAction,
    LineAction,
)
from .context import (
    ParsingContext,
    
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

        # Jump to next line
        if frame.finished_line:
            return frame.events

        events.extend(frame.events)

        # Update possible cursor advancement during continue check.
        line = frame.line

        logger.debug(f'--- Stage: try open ----')
        # Check for new container
        frame = self._try_open_new_frame(
            frame.last_matched_idx,
            line,
        )
        logger.debug(f'Frame after exhausting opening rules: {frame}')

        events.extend(frame.events)
        
        # Stop if the whole line is eaten.
        if frame.finished_line:
            logger.debug(f'--- Finished a line due to open')
            return events

        logger.debug(f'--- Stage: close unmatched if not lazy ---')

        line, close_events = self._close_unmatched_if_not_lazy(
            last_matched_idx=frame.last_matched_idx,
            new_starts_created=frame.new_starts_created,
            line=line,
        )

        events.extend(close_events)

        logger.debug(f'--- Stage: consume rest line ---')
        # add paragraph by default if there's text
        text_events = self._consume_line_text(
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

        last_matched_idx = -1
        is_line_finished = False
        is_explicit_close = False # True indicates explicitly closed element appeared.
        events: List[Event] = []

        # 1. Determine if the top of curent stack has a raw block like CodeBlock.
        has_raw_barrierr = (self.state.raw_barrier_idx != -1)

        for idx, frame in enumerate(self.state.frame_stack):
            
            # Skip leading spaces of current frame and 
            # go to the first non-space char.
            # This is NOT skipping leading space of a line.
            line = self.state.cursor.skip_frame_space(line)

            # If current container contains a raw text block,
            # flag it as is_covered, indicating that you are shadowed
            # by inner containers, yield your right to children.
            is_covered = has_raw_barrierr and (idx < self.state.raw_barrier_idx)

            cont_res = frame.on_continue(ParsingContext(
                cursor=self.state.cursor,
                line=line,
                is_covered=is_covered,
            ))

            logger.debug(f'{frame} continue result: {cont_res}')

            if cont_res.line_action == LineAction.CONSUMED:
                is_line_finished = True

            if cont_res.block_end is not None:
                line = cont_res.block_end
            
            events.extend(cont_res.events)

            match cont_res.action:
                case ContinueAction.STOP:
                    break

                case ContinueAction.CLOSE:
                    is_explicit_close = True
                    break

                case ContinueAction.CONTINUE:
                    last_matched_idx = idx
                    

        # Close expplicitly closed elements such as
        # code block, fenced div.
        if is_explicit_close:
            close_events = self.state.close_frame_to_depth(
                last_matched_idx,
                line,
            )
            # Ensure proper order since continued events
            # should not come before previous elements' closed events.
            events = close_events + events

        return LineStepFrame(
            line=line,
            last_matched_idx=last_matched_idx, 
            finished_line=is_line_finished,
            events=events, 
        )

    def _try_open_new_frame(
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
            logger.debug(f'{line.pos}. Current cursor has moved to EOL after skipping frame space. Stop.')
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
            # Guard if there's any rule applied.
            more_frames_required = False

            logger.debug(f'{line.pos} --- Start trying rules')

            # This loop breaks the moment a match is applied.
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

                result = rule.try_open(ParsingContext(
                    cursor=self.state.cursor,
                    line=line,
                ))

                match result.status:
                    case  OpenStatus.NOT_MATCHED:
                        logger.debug(f'{line.pos}. {rule.__class__.__name__} cannot open. Try next rule.')
                        continue

                    case OpenStatus.FALLBACK:
                        logger.debug(f'{line.pos}. {rule.__class__.__name__} fallback. Stop.')
                        # TODO: disable attributes
                        _, para_events = self._open_para(last_matched_idx, result.block_start)
                        
                        last_matched_idx = len(self.state.frame_stack) - 1
                        events.extend(para_events)

                        return LineStepFrame(
                            line=line,
                            last_matched_idx=last_matched_idx,
                            events=events,
                        )

                    case OpenStatus.MATCHED:
                        logger.debug(f'{line.pos}. {rule.__class__.__name__} matched.')

                        events.extend(self._handle_matched(last_matched_idx, result))

                        if result.frame is not None:
                            last_matched_idx = len(self.state.frame_stack)-1
                            parent = self.state.frame_stack[last_matched_idx]

                        if result.block_end is not None:
                            line = result.block_end
                        
                        line = self.state.cursor.skip_frame_space(line)
                        new_starts_created = True

                        if rule.accepts_blocks():
                            more_frames_required = True
                            break

                        else:
                            return LineStepFrame(
                                line=line,
                                last_matched_idx=last_matched_idx,
                                new_starts_created=new_starts_created,
                                events=events
                            )
                    
                    case OpenStatus.MATCH_AND_CONSUMED:
                        events.extend(self._handle_matched(last_matched_idx, result))
                        
                        if result.frame is not None:
                            last_matched_idx = len(self.state.frame_stack)-1

                        if result.block_end is not None:
                            line = result.block_end

                        return LineStepFrame(
                            line=line,
                            last_matched_idx=last_matched_idx,
                            finished_line=True,
                            new_starts_created=True,
                            events=events
                        )


            logger.debug(f'{line.pos}. Exhausted all rules. Opened any: {more_frames_required}')
            if not more_frames_required:
                break
        
        return LineStepFrame(
            line=line,
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
            result.block_start
        )

        if result.frame is not None:
            sibling_events = self.state.close_frame_to_parent(
                result.frame,
                result.block_start
            )
            events.extend(sibling_events)
            self.state.push_frame(result.frame)

        events.extend(result.events)

        return events


    def _close_unmatched_if_not_lazy(
        self,
        last_matched_idx: int,
        new_starts_created: bool,
        line: LineContext,
    ) -> Tuple[LineContext, List[Event]]:
        """
        Check if the following content is lazy.
        For example,

        > Blockquote paragraph
        Paragraph continnued.
        """
        line = self.state.cursor.skip_frame_space(line)

        is_eol = line.is_reaching_end
        
        tip = self.state.top_frame

        is_lazy = (
            not is_eol
            and not new_starts_created # If we created a new container, and the container has trailing content, do not trigger lazy continuation
            and last_matched_idx < len(self.state.frame_stack) - 1 # not last one
            and tip is not None
            and tip.rule.accepts_inline_only() # paraggraph, heading, caption
        )

        if not is_lazy:
            logger.debug(f'{line.pos}. Not lazy content. Close containers to {last_matched_idx}.')
            
            events = self.state.close_frame_to_depth(
                last_matched_idx,
                line,
            )

            return line, events

        return line, []

    def _consume_line_text(
        self,
        last_matched_idx: int,
        new_starts_created: bool, # true only when opened new frame but not consumed whole line
        line: LineContext,
    ) -> List[Event]:
        """
        Fallback dispatcher.

        When reaching here, it indicates outer container are all matched, or closed.
        Now we have to decide to where the rest of line should go based on
        top container's capability.

        There are 3 cases of container type:
        1. The top container is block-only. It cannot hold text.
           So we have to create a child node.
           For blankline, create blanline event
           If there are contents, create a paragraph node.
        2. The top container is text leaf. It hold verbatim text only
        3. The top container is inline.
        """

        frame = self.state.top_frame

        events = []
        is_eol = line.is_reaching_end

        if frame is None:
            frame, events = self._create_root_para(line)
            last_matched_idx = len(self.state.frame_stack)

        # Case 1: top stack is block container.
        if frame.rule.accepts_block_only():
            if is_eol:
                # Blankline inside block-only container
                return [self._parse_blankline(line, frame)]
            else:
                # Non-blank content inside block-only container
                frame, para_events = self._open_para(last_matched_idx, line)
                events.extend(para_events)

        # Top container is text leaf.
        if frame.rule.accepts_text_only():
            events.append(self._parse_text(frame, line))
        # Top container is inline.
        elif frame.rule.accepts_inline_only and not is_eol:
            self._parse_inline(frame, line)

        return events

    def _create_root_para(self, line: LineContext) -> Tuple[BlockFrame, List[Event]]:
        # djot.js used a complicated logic by mixing two conditions:
        # `if (!tip || tip.content === ContentType.Block)`
        # I think tip is null simply means there is no top container,
        # indicating we are at the root level of a document.
        # So create a fallback paragraph.
        # Root level blankline is useless. 
        # Simply ignore the original `if (isBlank)` case.
        result = self.para_rule.try_open(ParsingContext(
            cursor=self.state.cursor,
            line=line,
        ))
        assert result.frame is not None

        frame = self.state.push_frame(result.frame)

        return frame, result.events

    def _open_para(self, last_matched_idx: int, line: LineContext) -> Tuple[BlockFrame, List[Event]]:
        logger.debug(f'{line.pos}. Fallback to paragraph.')

        events: List[Event] = []

        open_res = self.para_rule.try_open(ParsingContext(
            cursor=self.state.cursor,
            line=line,
        ))

        # ParaRule could always open a new container.
        assert open_res.frame is not None

        closed_events = self.state.close_frames(
            last_matched_idx,
            open_res.frame,
            line
        )

        events.extend(closed_events)
        events.extend(open_res.events)
        
        frame = self.state.push_frame(
            open_res.frame,
        )

        return frame, events

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

    def _parse_blankline(self, line: LineContext, tip: BlockFrame) -> Event:
        line_end = line.end_offset

        if tip.closing_boundary:
            # Solve a problem of blankline nested in a block container.
            # Move parent block's closing boundary.
            # TODO: is there a more elegant way?
            tip.update_closing_boundary(line_end, line_end)
        
        return Event.leaf(
            kind=BlockLeaf.BLANKLINE,
            span=self.state.cursor.new_span(line_end, line_end)
        )
    

    def parse(self) -> Iterator[Event]:
        next_line = self.state.cursor.next_line(LineContext())

        while next_line is not None:
            line_events = self.process_line(next_line)

            for event in line_events:
                yield event

            next_line = self.state.cursor.next_line(next_line)

        if self.state.cursor.current_line is not None:
            logger.debug(f'Cleanup.')
            for event in self.state.close_frame_to_depth(-1, self.state.cursor.current_line):
                yield event

