from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from djot.ast import (
    AstNode,
    Reference,
    Footnote,
)
from djot.common import (
    Pos,
    SourceMap,
)
from djot.event import (
    Event,
    BlockContainer,
)

from .frame import Frame
from .attr import AttrBuilder

class Mode(Enum):
    NORMAL = 0
    VERBATIM = 1
    LITERAL = 2
    
class DocumentContext:

    def __init__(self, src: str, source_location: bool = False):
        self.src = src
        self.source_map: SourceMap | None = SourceMap(src) if source_location else None

    def get_leaf_text(self, event: Event) -> str:
        return self.src[event.startpos:event.endpos+1]

    def get_text(self, start: int, end: int) -> str:
        return self.src[start:end]

    def calc_pos(self, start: int, end: int) -> Pos | None:
        if not self.source_map:
            return None
        
        return self.source_map.calc_pos(start, end)

    def calc_leaf_pos(self, event: Event) -> Pos | None:
        if not self.source_map:
            return None
        return self.source_map.calc_pos(event.startpos, event.endpos)

    def calc_container_pos(self, frame: Frame, event: Event) -> Pos | None:
        if not self.source_map:
            return None
        return self.source_map.calc_pos(frame.start_pos, event.endpos)

@dataclass(slots=True)
class BuildingState:
    stack: list[Frame] = field(default_factory=list)
    
    
    # 跨事件暂存状态
    block_attributes: AttrBuilder = field(default_factory=AttrBuilder)
    list_depth: int = 0
    
    # 纯文本缓冲（Verbatim/CodeBlock 等专用）
    mode: Mode = Mode.NORMAL
    text_buffer: list[str] = field(default_factory=list)

    references: Dict[str, Reference] = field(default_factory=dict)
    footnotes: Dict[str, Footnote] = field(default_factory=dict)

    @property
    def current_frame(self) -> Frame:
        if not self.stack:
            raise RuntimeError("Frame stack is empty (top_frame)")
        return self.stack[-1]

    @property
    def last_node(self) -> Optional[AstNode]:
        frame = self.current_frame
        if frame.children:
            return frame.children[-1]
        return None

    def push_frame(self, frame: Frame):
            self.stack.append(frame)
    
    def pop_frame(self) -> Frame:
        if not self.stack:
            raise RuntimeError("Frame stack is empty (pop_frame)")
        return self.stack.pop()

    def find_list_frame(self) -> Frame | None:
        # Top frame is a list. So we are inside a list but outside list items.
        if self.current_frame.kind == BlockContainer.LIST:
            return self.current_frame

        # Top frame is a list item. So we are inside a list item of a list.
        if len(self.stack) >= 2 and self.stack[-2].kind == BlockContainer.LIST:
            return self.stack[-2]

        return None

    
    def add_reference(self, reference: Reference) -> None:
        self.references[reference.label] = reference

    def add_footnote(self, footnote: Footnote):
        self.footnotes[footnote.label] = footnote

    def switch_to_normal(self):
        self.mode = Mode.NORMAL

    def switch_to_literal(self):
        self.mode = Mode.LITERAL

    def switch_to_verb(self):
        self.mode = Mode.VERBATIM

    def add_child_to_tip(self, child: AstNode):
        self.current_frame.add_child(child)

    def replace_last_node(self, node: AstNode):
        self.current_frame.replace_child(node, -1)