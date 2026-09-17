from dataclasses import dataclass, field
from typing import Any, Iterator, List, NamedTuple, Optional


from ..inline import InlineParser
from ..input import InputText
from ..event import (
    Event,
    Action,
    ElementKind
)
from ..options import Options
from ..common import Range

from .rule import (
    ContainerCap,
    Container,
    FlowControl,
    RuleResult,
    BlockRule,
    ParaRule,
    BlockquoteRule,
    HeadingRule,
    CaptionRule,
    FootnoteRule,
    ReferenceDefinitionRule,
    ThematicBreakRule,
    ListRule,
    ListItemRule,
    TableRule,
    AttributeRule,
    FencedDivRule,
    CodeBlockRule,
)


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

        self.events: List[Event] = []

        # A container stack describes a path in a tree from root to a leaf.
        # When we push a new container, we are exiting a node and switch to a sibling.
        self.container_stack: List[Container[Any]] = []
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

    @property
    def top_container(self) -> Optional[Container]:
        """获取当前 AST 活跃路径中最内层的容器节点"""
        return self.container_stack[-1] if self.container_stack else None

    @property
    def last_event(self) -> Optional[Event]:
        if self.events:
            return self.events[-1]

        return None

    @property
    def last_event_endpos(self) -> Optional[int]:
        if self.events:
            return self.events[-1].span.end

        return None
        

    def last_matched_container(self, idx: int) -> Optional[Container]:
        if not self.container_stack:
            return None
        if idx < 0 or idx >= len(self.container_stack):
            return None

        return self.container_stack[idx]

    def _push_container(
        self, 
        container: Container, 
    ) -> Container:

        # Clear all siblings and their children before attaching a new child.
        closed_events = self._close_siblings_of(container)

        if container.children_type == ContainerCap.INLINE:
            # Why not attach the InlineParser when the container is created?
            # Or attach it lazily when it is first accessed?
            # Why here?
            container.inline_parser = InlineParser(
                cursor=self.input, 
                options=self.options,
            )

        self.container_stack.append(container)
        return container

    def _close_siblings_of(self, new_container: Container) -> List[Event]:
        events: List[Event] = []

        while self.container_stack:
            if self.container_stack[-1].can_nest(new_container):
                break

            top = self.container_stack.pop()

            close_result = top.close(self.input, self.last_event_endpos)
            events.extend(close_result.events)


        return events

    def _close_container_to_depth(
        self,
        last_matched_idx: int
    ) -> List[Event]:
        """ Close containers from innermost element to the specified index (exclusive).

        In a tree view, it closes all children nodes under last_matched_idx.

        Args:
            last_matched_idx (int): The index of the last matched container. -1 means close all.

        Retursn:
            List[Event]: The events collected in close step.
        """

        events: List[Event] = []

        while self.container_stack and len(self.container_stack)-1 > last_matched_idx:
            top = self.container_stack.pop()

            close_result = top.close(self.input, self.last_event_endpos)
            events.extend(close_result.events)

        return events

    def process_line(self) -> List[Event]:
        self.input.start_newline()

        events: List[Event] = []

        # 1. Check container continuation (Step 1)
        cont_result = self._check_continuations()
        
        events.extend(cont_result.events)

        # If Step 1 gobbles whole line, close the container and return
        if cont_result.finished_line:
            close_events = self._close_container_to_depth(cont_result.last_matched_idx)
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

        for idx, container in enumerate(self.container_stack):
            # 1. Prepare cursor for rule
            self.input.skip_space()

            res = container.try_continue(self.input)

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
        result = OpenContainerResult(
            last_matched_idx=last_matched_idx
        )

        # Fast Pass Guard
        self.input.skip_space()
        if self.input.is_blank_line:
            return result

        # If found last matched container, but the container does not allow
        # block type as its child, stop.
        last_match = self.last_matched_container(last_matched_idx)
        if last_match:
            if not last_match.can_child_be_block:
                return result

        # Why finding words stops?
        if self.input.find_word():
            return result

        # Cascade Open
        while True:
            opend_any = False

            for rule in self.block_rules:
                # Check container nesting if stack top container permit current rule to be nested
                if not rule.can_be_root_or_nested(last_match):
                    continue

                open_res: RuleResult = rule.try_open(self.input)

                if open_res.status == FlowControl.OPEN:
                    if open_res.events:
                        result.events.extend(open_res.events)

                    tip = open_res.container
                    if not tip:
                        raise Exception('No tip after opening cotainer')

                    # Explicitly close sibling containers before adding current one.
                    closed_events = self._close_siblings_of(tip)
                    result.events.extend(closed_events)

                    tip = self._push_container(tip)

                    # Update last matched index after stack push.
                    result.last_matched_idx = len(self.container_stack)-1
                    result.new_starts_created = True

                    last_match = tip
                    opend_any = True

                    # If the whole line is handle by the the open action.
                    if open_res.finished_line:
                        result.finished_line = True
                        return result

                    # Not end of line. Skip space and try another rule.
                    self.input.skip_space()

                    # If current rule does not accept blocks as its children.
                    if not rule.accepts_blocks():
                        return result

            # After exhausting all rules, no one applies.
            if not opend_any:
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
        tip = self.top_container

        # 判定是否为 Lazy Paragraph Continuation
        is_lazy = (
            not self.input.is_blank_line
            and not new_starts_created
            and last_matched_idx < len(self.container_stack) - 1 # not last one
            and tip is not None
            and tip.rule.accepts_inline_only()
        )

        if not is_lazy:
            # Stack might change here.
            # Therefore djot.js perform tip = self.tip() again after here.
            events.extend(self._close_container_to_depth(last_matched_idx))

        return events

    def _consume_line_text(
        self,
        new_starts_created: bool,
    ) -> List[Event]:
        events = []
        is_blank = self.input.is_blank_line
        tip = self.top_container

        if tip is None or tip.rule.accepts_block_only():
            if is_blank:
                if not new_starts_created:
                    # need to track these for tight/loose lists.
                    events.append(
                        Event(
                            action=Action.NONE,
                            kind=ElementKind.BLANKLINE,
                            span=self.input.current_line_span()
                        )
                    )
                return events
            else:
                # In djot.js, open paragraph adds a new container and event.
                open_result = self.para_rule.try_open(self.input)
                # ParaRule could always open a new container.
                assert open_result.container is not None

                closed_events = self._close_siblings_of(open_result.container)
                events.extend(closed_events)
                
                para_container = self._push_container(open_result.container)
                events.extend(open_result.events)

                tip = para_container

        if tip.rule.accepts_text_only(): # if child node is text only.
            start_pos = self.input.get_adjusted_text_start(tip.indent)
            events.append(
                Event(
                    action=Action.NONE,
                    kind=ElementKind.STR,
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


        for event in self._close_container_to_depth(-1):
            yield event

