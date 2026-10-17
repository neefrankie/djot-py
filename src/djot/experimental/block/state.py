from typing import List, Optional

from djot.logger import logger
from djot.event import (
    Event,
)
from djot.inline import InlineParser

from ..cursor import Cursor, LineContext
from .frame import (
    BlockFrame,
    ContainerCap,
    ParsingContext,
    RuleResult,
)

class BlockState:
    def __init__(self, cursor: Cursor):
        self.cursor = cursor

        # A container stack describes a path in a tree from root to a leaf.
        # When we push a new container, we are exiting a node and switch to a sibling.
        self.frame_stack: List[BlockFrame] = []
        # Index of container with opaque content, a block of raw text
        # with higher precedence shadowing outer container.
        # -1 mean the stack does not have such a container.
        self.raw_barrier_idx: int = -1

    @property
    def top_frame(self) -> Optional[BlockFrame]:
        """Get the innermost node in current active AST path"""
        return self.frame_stack[-1] if self.frame_stack else None

    def last_matched_frame(self, idx: int) -> Optional[BlockFrame]:
        if not self.frame_stack:
            return None
        if idx < 0 or idx >= len(self.frame_stack):
            return None

        return self.frame_stack[idx]

    def push_frame(
        self, 
        frame: BlockFrame,
    ) -> BlockFrame:

        if frame.children_type == ContainerCap.INLINE:
            # Why not attach the InlineParser when the container is created?
            # Or attach it lazily when it is first accessed?
            # Why here?
            frame.inline_parser = InlineParser(
                cursor=self.cursor, 
            )

        self.frame_stack.append(frame)

        # If new container is opaquee like CodeBlock,
        # and there is no record of such container, remember its index.
        if frame.accepts_raw_text and self.raw_barrier_idx == -1:
            self.raw_barrier_idx = len(self.frame_stack) - 1

        return frame

    def close_frames(
        self,
        last_matched_idx: int,
        new_frame: BlockFrame,
        line: LineContext,
    ) -> List[Event]:
        unmatched = self.close_frame_to_depth(last_matched_idx, line)
        siblings = self.close_siblings_of(new_frame, line)
        return unmatched + siblings

    def pop_frame(self) -> Optional[BlockFrame]:
        if not self.frame_stack:
            return None

        top = self.frame_stack.pop()

        # If the popped container happens to be the shadowing container,
        # reset index.
        if len(self.frame_stack) <= self.raw_barrier_idx:
            self.raw_barrier_idx = -1

        return top

    def close_siblings_of(
        self,
        new_frame: BlockFrame,
        line: LineContext
    ) -> List[Event]:
        """Close sibling nodes when pushing a new container"""
        logger.debug(f'close siblings of {new_frame}. current stack: {len(self.frame_stack)}')
        events: List[Event] = []

        while self.frame_stack:
            if self.frame_stack[-1].can_cantain(new_frame):
                break

            top = self.pop_frame()
            if not top:
                break

            close_result = self._close_frame(top, line)
            events.extend(close_result.events)


        return events

    def _close_frame(self, frame: BlockFrame, line: LineContext) -> RuleResult:
        events: List[Event] = []
        if frame.inline_parser:
            events.extend(frame.inline_parser.iter_merged_events())
        

        logger.debug(f'🚪{line.pos}. Close {frame}')
        result = frame.on_close(ParsingContext(
            cursor=self.cursor,
            line=line,
        ))
        result.events = events + result.events
        return result


    def close_frame_to_depth(
        self,
        last_matched_idx: int,
        line: LineContext
    ) -> List[Event]:
        """ Close containers from innermost element to the specified index (exclusive).

        In a tree view, it closes all children nodes under last_matched_idx.

        Args:
            last_matched_idx (int): The index of the last matched container. -1 means close all.

        Retursn:
            List[Event]: The events collected in close step.
        """
        logger.debug(f'Close container to depth {last_matched_idx}, current stack: {len(self.frame_stack)}')
        events: List[Event] = []

        while self.frame_stack and last_matched_idx < len(self.frame_stack)-1:
            top_frame = self.pop_frame()
            if not top_frame:
                break

            close_result = self._close_frame(
                top_frame,
                line
            )
            events.extend(close_result.events)

        return events