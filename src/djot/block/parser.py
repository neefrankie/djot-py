from dataclasses import dataclass, field
from typing import Iterator, List, NamedTuple, Optional


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


class ContinueContainerResult(NamedTuple):
    last_matched_idx: int
    events: List[Event]
    finished_line: bool

@dataclass
class OpenContainerResult:
    last_matched_idx: int
    new_starts_created: bool = False
    events: List[Event] = field(default_factory=list)
    finished_line: bool = False


class EventParser:
    def __init__(self, src: str, options: Options | None = None) -> None:
        self.input = InputText(src)
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
        self.input.start_newline()

        events: List[Event] = []

        # 1. Check container continuation (Step 1)
        cont_result = self._check_continuations()
        
        events.extend(cont_result.events)

        # If Step 1 gobbles whole line, close the container and return
        if cont_result.finished_line:
            close_events = self.state.close_container_to_depth(cont_result.last_matched_idx)
            events.extend(close_events)
            return events

        self.input.skip_space()

        # 2.Try to open new container (Check New Starts)
        open_result = self._try_open_new_cotainer(
            cont_result.last_matched_idx
        )

        # 3. Cleanup and close unmatched container (Close Unmatched)
        closure_events = self._handle_container_closures(
            last_matched_idx=open_result.last_matched_idx,
            new_starts_created=open_result.new_starts_created,
        )
        events.extend(closure_events)

        text_events = self._consume_line_text(
            open_result.new_starts_created
        )
        events.extend(text_events)

        return events

    def _check_continuations(self) -> ContinueContainerResult:
        """沿容器栈自顶向下/自底向上检查续约（Check Open Containers）
        
        为什么用 while 按数组顺序（idx = 0）遍历？

        `self.containers` 数组是一个栈，索引 `0` 是最外层的容器（比如文档根节点 Document 或最外层的 BlockQuote），索引越靠后，层级越深（比如内层的 List）。

        检查续约必须从外向内（自底向上）检查！因为如果最外层的 BlockQuote 在这一行失效了（比如这一行没写 `>`），那么它里面嵌套的 List 就算写得再符合规范，也失去了存在的语义土壤。
        """
        last_matched_idx = -1
        events: List[Event] = []
        line_is_finished = False

        # 1. Determine if the top of curent stack has a raw block like CodeBlock.
        has_raw_barrierr = (self.state.raw_barrier_idx != -1)

        for idx, container in enumerate(self.state.container_stack):
            # 1. Prepare cursor for rule
            self.input.skip_space()

            # 2. If current container contains a raw text block,
            # flag it as is_covered, indicating that you are shadowed
            # by inner containers, yield your right to children.
            is_covered = has_raw_barrierr and (idx < self.state.raw_barrier_idx)

            res = container.on_continue(ParsingContext(
                cursor=self.input,
                is_covered=is_covered,
            ))

            if res == FlowControl.CONTINUE:
                last_matched_idx = idx
                if res.events:
                    events.extend(res.events)

                    if res.finished_line:
                        line_is_finished = True
                        break # If the line is processed, stop.
            else:
                # The moment a container cannot continue, stop immediately
                break

            idx = idx + 1

        return ContinueContainerResult(
            last_matched_idx=last_matched_idx,
            events=events, 
            finished_line=line_is_finished
        )

    def _try_open_new_cotainer(self, last_matched_idx: int) -> OpenContainerResult:
        # Fast Pass Guard
        self.input.skip_space()
        if self.input.is_blank_line:
            return OpenContainerResult(last_matched_idx)

        # If found last matched container, but the container does not allow
        # block type as its child, stop.
        parent = self.state.last_matched_container(last_matched_idx)
        if parent and not parent.accepts_block:
                return OpenContainerResult(last_matched_idx)

        # Why finding words stops?
        if self.input.find_word():
            return OpenContainerResult(last_matched_idx)

        # Cascade Open
        return self._apply_rules(parent, last_matched_idx)

    def _apply_rules(self, parent: Optional[Container], parent_idx: int):
        
        result = OpenContainerResult(
            last_matched_idx=parent_idx
        )

        while True:
            opened_any = False

            for rule in self.block_rules:
                # Check relationship to parent element.
                if parent and not parent.can_nest(rule):
                    continue
                elif not rule.can_be_root():
                    continue

                open_res = rule.try_open(self.input)

                if open_res.status != FlowControl.OPEN:
                    continue

                if open_res.events:
                    result.events.extend(open_res.events)

                if open_res.container is None:
                    raise Exception('No container created after opening an element')

                # Explicitly close sibling containers before adding current one.
                closed_events = self.state.close_siblings_of(open_res.container)
                parent = self.state.push_container(open_res.container, self.options)

                result.events.extend(closed_events)
                result.last_matched_idx = len(self.state.container_stack)-1
                result.new_starts_created = True

                opened_any = True

                if open_res.finished_line:
                    result.finished_line = True
                    return result

                self.input.skip_space()

                if not rule.accepts_blocks():
                    return result

            if not opened_any:
                break
        
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
            not self.input.is_blank_line
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
        new_starts_created: bool,
    ) -> List[Event]:
        events = []
        is_blank = self.input.is_blank_line
        tip = self.state.top_container

        if tip is None or tip.rule.accepts_block_only():
            if is_blank:
                if not new_starts_created:
                    # need to track these for tight/loose lists.
                    events.append(
                        Event.leaf(
                            kind=BlockLeaf.BLANKLINE,
                            span=self.input.rest_line_span()
                        )
                    )
                return events
            else:
                # In djot.js, open paragraph adds a new container and event.
                open_result = self.para_rule.try_open(self.input)
                # ParaRule could always open a new container.
                assert open_result.container is not None

                closed_events = self.state.close_siblings_of(open_result.container)
                events.extend(closed_events)
                
                para_container = self.state.push_container(open_result.container, self.options)
                events.extend(open_result.events)

                tip = para_container

        if tip.rule.accepts_text_only(): # if child node is text only.
            start_pos = self.input.get_adjusted_text_start(tip.indent)
            events.append(
                Event.leaf(
                    kind=InlineLeaf.STR,
                    span=Range(
                        start=start_pos,
                        end=self.input.eol_start,
                    )
                )
            ) # gobble the whole line.
        elif tip.rule.accepts_inline_only and not is_blank: # if child nodes are inline elements.
            if tip.inline_parser: # guard inline parse is set.
                tip.inline_parser.feed(self.input.pos, self.input.eol_start)

        return events

    def parse(self) -> Iterator[Event]:
        while not self.input.is_eof():
            line_events = self.process_line()

            for event in line_events:
                yield event

            self.input.advance_to_new_line()


        for event in self.state.close_container_to_depth(-1):
            yield event

