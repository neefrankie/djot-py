from typing import Any, List, Optional

from ..logger import logger
from ..options import Options
from ..input import InputText
from ..event import (
    Event,
)
from ..inline import InlineParser
from .container import (
    Container,
    ContainerCap,
    ParsingContext,
    RuleResult,
)

class BlockState:
    def __init__(self, cursor: InputText):
        self.cursor = cursor

        # A container stack describes a path in a tree from root to a leaf.
        # When we push a new container, we are exiting a node and switch to a sibling.
        self.container_stack: List[Container[Any]] = []
        # Index of container with opaque content, a block of raw text
        # with higher precedence shadowing outer container.
        # -1 mean the stack does not have such a container.
        self.raw_barrier_idx: int = -1

        # This is a strange hack.
        self.last_event: Optional[Event] = None

    @property
    def top_container(self) -> Optional[Container]:
        """Get the innermost node in current active AST path"""
        return self.container_stack[-1] if self.container_stack else None

    def start_newline(self):
        self.cursor.start_newline()

    def skip_space(self):
        self.cursor.skip_space()

    def get_adjusted_text_start(self, indent: int | None):
        return self.cursor.get_adjusted_text_start(indent)

    def last_matched_container(self, idx: int) -> Optional[Container]:
        if not self.container_stack:
            return None
        if idx < 0 or idx >= len(self.container_stack):
            return None

        return self.container_stack[idx]

    def push_container(
        self, 
        container: Container,
        options: Options
    ) -> Container:

        if container.children_type == ContainerCap.INLINE:
            # Why not attach the InlineParser when the container is created?
            # Or attach it lazily when it is first accessed?
            # Why here?
            container.inline_parser = InlineParser(
                cursor=self.cursor, 
                options=options,
            )

        self.container_stack.append(container)

        # If new container is opaquee like CodeBlock,
        # and there is no record of such container, remember its index.
        if container.accepts_raw_text and self.raw_barrier_idx == -1:
            self.raw_barrier_idx = len(self.container_stack) - 1

        return container

    def close_containers(self, last_matched_idx: int, new_container: Container) -> List[Event]:
        unmatched = self.close_container_to_depth(last_matched_idx)
        siblings = self.close_siblings_of(new_container)
        return unmatched + siblings

    def pop_containier(self) -> Optional[Container]:
        if not self.container_stack:
            return None

        top = self.container_stack.pop()

        # If the popped container happens to be the shadowing container,
        # reset index.
        if len(self.container_stack) <= self.raw_barrier_idx:
            self.raw_barrier_idx = -1

        return top

    def close_siblings_of(
        self,
        new_container: Container
    ) -> List[Event]:
        """Close sibling nodes when pushing a new container"""
        logger.debug(f'close siblings of {new_container}. current stack: {len(self.container_stack)}')
        events: List[Event] = []

        while self.container_stack:
            if self.container_stack[-1].can_cantain(new_container):
                break

            top = self.pop_containier()
            if not top:
                break

            close_result = self._close_container(top)
            events.extend(close_result.events)


        return events

    # This is a horrible hack.
    def update_last_event(self, events: List[Event]):
        if events:
            self.last_event = events[-1]

    def _close_container(self, container: Container) -> RuleResult:
        events: List[Event] = []
        if container.inline_parser:
            events.extend(container.inline_parser.iter_merged_events())
        self.update_last_event(events)

        logger.debug(f'🚪{self.cursor.pos}. Close {container}')
        result = container.on_close(ParsingContext(
            cursor=self.cursor,
            last_span_end=self.last_event.span.end if self.last_event else None
        ))
        result.events = events + result.events
        return result


    def close_container_to_depth(
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
        logger.debug(f'Close container to depth {last_matched_idx}, current stack: {len(self.container_stack)}')
        events: List[Event] = []

        while self.container_stack and last_matched_idx < len(self.container_stack)-1:
            top = self.pop_containier()
            if not top:
                break

            close_result = self._close_container(top)
            events.extend(close_result.events)

        return events