from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, cast

from ..logger import logger
from ..event import (
    Event,
    BlockContainer,
    VerbatimKind,
    InlineContainer,
    InlineLeaf,
    AttrKind,
    Action,
    ListPayload as ListEventData
)
from ..ast.base import (
    Attributes,
    merge_attributes,
    AstNode,
)
from ..ast.inline import (
    Str,
    SoftBreak,
    HardBreak,
    NonBreakingSpace,
    Symb,
    Verbatim,
    RawInline,
    InlineMath,
    DisplayMath,
    Url,
    Email,
    FootnoteReference,
    Emph,
    Strong,
    Link,
    Image,
    Span,
    Mark,
    Superscript,
    Subscript,
    Insert,
    Delete,
    DoubleQuoted,
    SingleQuoted,
)
from ..ast.block import (
    Para,
    Heading,
    Reference
)
from ..ast.list import (
    TaskList,
    BulletList,
    OrderedList,
    DefinitionList,
    BulletListStyle,
    OrderedListStyle,
)
from ..ast.doc import Doc

from ..common import Pos

from .roman import get_list_start
from .normalize import (
    normalize_label,
    trim_verbatim,
    normalize_raw_format,
    remove_newline,
)
from .location import get_source_loc, get_line_starts

from .frame import (
    Frame,
    ListData,
)

class Context(Enum):
    Normal = 0
    Verbatim = 1
    Literal = 2

    
@dataclass(slots=True)
class ExitResult:
    node: AstNode | None = None
    context: Context | None = None
    clear_text_buffer: bool = False
    block_attributes: Attributes | None = None

class ASTBuidler:
    def __init__(self, src: str, events: List[Event]):
        self.src = src
        self.events = events
        self.stack: List[Frame] = []

        self.line_starts = get_line_starts(self.src)

        self.context: Context = Context.Normal

        # Bufffer text for plain text node like verbatim / code block
        self.text_buffer: List[str] = []
        # Reference link definition is collected here.
        # The buildonig processs is scattered around:
        # Event(Enter): push to stack
        # Event(Key): set to the top stack element
        # Event(Value): apppended to the top stack element
        # Event(Exit): popped from container the added herer rathaer than parent node.
        self.references: Dict[str, Reference] = {}

        # Buffer attributes before parsing a block.
        self.block_attributes: Attributes = {}

        self.list_depth = 0

    @property
    def accumulated_text(self) -> str:
        return ''.join(self.text_buffer)

    def switch_to_normal(self):
        self.context = Context.Normal

    def switch_to_literal(self):
        self.context = Context.Literal

    def clear_text_buffer(self):
        self.text_buffer = []

    def build(self):
        root_frame = Frame(
            kind=BlockContainer.DOC,
            start_pos=0,
            children=[],
        )
        self.stack.append(root_frame)

        for event in self.events:
            self._dispatch_event(event)

        doc = Doc(
            children=root_frame.pop_block_children(),
            references={},
            footnotes={}
        )
        return doc

    def _dispatch_event(self, event: Event):
        if event.action:
            if event.action == Action.ENTER:
                self._handle_enter(event)
            elif event.action == Action.EXIT:
                self._handle_exit(event)
        else:
            self._handle_leaf(event)

    def _handle_enter(self, event: Event):
        frame = self._create_frame(event)

        if not frame:
            return

        # Attach block attributes to current block
        if self.block_attributes:
            frame.merge_attributes(self.block_attributes)
            # Clear after transfered.
            self.block_attributes = {}

        self.stack.append(frame)

    def _create_frame(self, enter_event: Event) -> Optional[Frame]:
        match enter_event.kind:
            case InlineContainer.LINK_TEXT:
                return Frame(
                    kind=enter_event.kind,
                    start_pos=enter_event.startpos,
                    is_image=False
                )
            case InlineContainer.IMAGE_TEXT:
                return Frame(
                    kind=enter_event.kind,
                    start_pos=enter_event.startpos,
                    is_image=True
                )
            case (InlineContainer.DESTINATION |
                  InlineContainer.REFERENCE):
                # No frame is created
                self.context = Context.Literal
                return None
            case (VerbatimKind.VERBATIM | 
                  VerbatimKind.DISPLAY_MATH):
                self.context = Context.Verbatim
                return Frame(
                    kind=enter_event.kind,
                    start_pos=enter_event.startpos
                )
            case (InlineContainer.URL |
                  InlineContainer.EMAIL):
                self.switch_to_literal()
                return Frame(
                    kind=enter_event.kind,
                    start_pos=enter_event.startpos
                )
            case BlockContainer.HEADING:
                return Frame(
                    kind=enter_event.kind,
                    start_pos=enter_event.startpos,
                    heading_level=len(enter_event),
                )
            case BlockContainer.LIST:
                self.list_depth += 1
                frame = Frame(
                    kind=enter_event.kind,
                    start_pos=enter_event.startpos,
                )
                if isinstance(enter_event.payload, ListEventData):
                    frame.with_list_styles(enter_event.payload.styles)
                return frame
            case _:
                return Frame(
                    kind=enter_event.kind,
                    start_pos=enter_event.startpos,
                )


    def _handle_exit(self, event: Event):
        frame = self.stack.pop()

        if frame.kind == BlockContainer.REFERENCE_DEFINITION:
            label = normalize_label(frame.get_ref_key())
            if label:
                self.references[label] = Reference(
                    attributes=frame.attributes, # TODO: why?
                    pos=self._calc_pos(
                        frame.start_pos,
                        event.endpos
                    ),
                    label=label,
                    destination=frame.get_ref_val(),
                            )
            return

        node = self._create_container_node(frame, event)
        if node is None:
            return
        
        self._add_child_to_tip(node)

    def _create_container_node(self, frame: Frame, exit_event: Event) -> Optional[AstNode]:
        """Create container node upon exit event."""

        pos = self._calc_pos(
            frame.start_pos,
            exit_event.endpos
        )

        match frame.kind:
            case InlineContainer.EMPH:
                return Emph(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.STRONG:
                return Strong(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.SPAN:
                return Span(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.MARK:
                return Mark(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.SUPERSCRIPT:
                return Superscript(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.SUBSCRIPT:
                return Subscript(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.DELETE:
                return Delete(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.INSERT:
                return Insert(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.DOUBLE_QUOTED:
                return DoubleQuoted(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.SINGLE_QUOTED:
                return SingleQuoted(
                    pos=pos,
                    children=frame.pop_inline_children(),
                )
            case InlineContainer.ATTR:
                return self._attach_inline_attr(frame)
            case BlockContainer.ATTRIBUTES:
                self._buffer_block_attr(frame)
                return None
            case InlineContainer.LINK_TEXT | InlineContainer.IMAGE_TEXT:
                # Do nothing when link text ends.
                return None
            case InlineContainer.DESTINATION:
                node = self._create_dest_node(frame, pos)
                self.context = Context.Normal
                return node

            case InlineContainer.REFERENCE:
                node = self._create_ref_node(frame, pos)
                self.context = Context.Normal
                return node
            case VerbatimKind.VERBATIM:
                node = Verbatim(
                    attributes=frame.attributes.copy(),
                    pos=pos,
                    text=self.accumulated_text
                )
                self.context = Context.Normal
                self.text_buffer = []
                return node
            case VerbatimKind.DISPLAY_MATH:
                node = DisplayMath(
                    attributes=frame.attributes.copy(),
                    pos=pos,
                    text=trim_verbatim(self.accumulated_text),
                )
                self.context = Context.Normal
                self.text_buffer = []
                return node
            case VerbatimKind.INLINE_MATH:
                node = InlineMath(
                    attributes=frame.attributes.copy(),
                    pos=pos,
                    text=trim_verbatim(self.accumulated_text),
                )
                self.context = Context.Normal
                self.text_buffer = []
                return node
            case InlineContainer.URL:
                node = Url(
                    attributes=frame.attributes,
                    pos=pos,
                    text=remove_newline(self.accumulated_text)
                )
                self.switch_to_normal()
                self.clear_text_buffer()
                return node
            case InlineContainer.EMAIL:
                node = Email(
                    attributes=frame.attributes,
                    pos=pos,
                    text=remove_newline(self.accumulated_text)
                )
                self.switch_to_normal()
                self.clear_text_buffer()
                return node
            case BlockContainer.PARA:
                return Para(
                    attributes=frame.attributes.copy(),
                    children=frame.pop_inline_children(),
                    pos=pos,
                )
            case BlockContainer.HEADING:
                return Heading(
                    attributes=frame.attributes.copy(),
                    pos=pos,
                    level=frame.heading_level or 0,
                    children=frame.pop_inline_children()
                )
            case BlockContainer.LIST:
                node = self._create_list_node(frame, pos)
                if node:
                    self.list_depth -= 1

                return node


    def _create_list_node(self, frame: Frame, pos: Pos):
        if not isinstance(frame.payload, ListData):
            raise Exception('No style defined for list')

        list_style = frame.payload.styles[0]
        if not list_style:
            raise Exception('No style defined for list')

        list_start = get_list_start(
            frame.meta['first_marker'],
            list_style,
        )
        if list_style == ':':
            return DefinitionList(
                attributes=frame.attributes.copy(),
                pos=pos,
                children=frame.pop_def_list_items()
            )
        if list_style.endswith('X'):
            return TaskList(
                attributes=frame.attributes.copy(),
                pos=pos,
                children=frame.pop_task_list_items(),
                tight=frame.payload.tight,
            )

        if list_style in ('+', '*', '-'):
            return BulletList(
                attributes=frame.attributes.copy(),
                pos=pos,
                children=frame.pop_list_item(),
                tight=frame.payload.tight,
                style=BulletListStyle(list_style)
            )

        return OrderedList(
            attributes=frame.attributes.copy(),
            pos=pos,
            children=frame.pop_list_item(),
            tight=frame.payload.tight,
            style=OrderedListStyle(list_style),
            start=list_start
        )
            

    def _create_dest_node(self, frame: Frame, pos: Pos) -> AstNode:
        dest = ''.join(self.text_buffer)
        self.text_buffer = []
        if frame.is_image:
            return Image(
                attributes=frame.attributes.copy(),
                pos=pos,
                children=frame.pop_inline_children(),
                destination=dest,
                reference=None
            )
        
        return Link(
            attributes=frame.attributes.copy(),
            pos=pos,
            children=frame.pop_inline_children(),
            destination=dest,
            reference=None,
        )

    def _create_ref_node(self, frame: Frame, pos: Pos) -> AstNode:
        ref = ''.join(self.text_buffer)
        if not ref:
            ref = ''.join(frame.iter_string_content())

        self.text_buffer = []

        if frame.is_image:
            return Image(
                attributes=frame.attributes.copy(),
                pos=pos,
                children=frame.pop_inline_children(),
                destination=None,
                reference=normalize_label(ref),
            )
        else:
            return Image(
                attributes=frame.attributes.copy(),
                pos=pos,
                children=frame.pop_inline_children(),
                destination=None,
                reference=normalize_label(ref)
            )

    def _attach_inline_attr(self, frame: Frame) -> Optional[AstNode]:
        """
        hello world{.red}: split at last space

        hello world {.red}: drop attributes
        """
        if not frame.attributes:
            return None

        if not self.stack:
            return None

        if not self.stack[-1].children:
            return None

        last_node = self.stack[-1].children[-1]
        if not isinstance(last_node, Str):
            last_node.merge_attributes(frame.attributes)
            return None

        if not last_node.text or last_node.text[-1].isspace():
            logger.warning(f'Ignoring unattached attribute: {get_source_loc(self.line_starts, frame.start_pos)}')
            return None

        new_node = last_node.split_at_last_space()
        if not new_node:
            last_node.merge_attributes(frame.attributes)
            return None

        new_node.merge_attributes(frame.attributes)

        return new_node

    def _buffer_block_attr(self, frame: Frame):
        """
        Cache block attributes so that they could
        be transfered to next block element.
        """
        if not frame.attributes:
            return

        if not self.stack:
            return

        self.block_attributes = merge_attributes(
            target=self.block_attributes,
            source=frame.attributes
        )
        

    def _handle_leaf(self, event: Event):
        assert event.action is None

        text_content = self.src[event.startpos:event.endpos+1]
        pos = self._calc_pos(event.startpos, event.endpos)

        if event.kind in AttrKind:
            self._process_attr_leaf(
                cast(AttrKind, event.kind),
                text_content
            )
            return
        
        match event.kind:
            case InlineLeaf.STR:
                if self.context == Context.Normal:
                    self._add_child_to_tip(Str(
                        text=text_content,
                        pos=pos,
                    ))
                else:
                    self.text_buffer.append(text_content)

            case InlineLeaf.SOFT_BREAK:
                # '\n'
                if self.context == Context.Normal:
                    self._add_child_to_tip(SoftBreak(
                        pos=pos
                    ))
                else:
                    self.text_buffer.append('\n')
            case InlineLeaf.ESCAPE:
                # TODO: why not kee escape in normal mode?
                if self.context == Context.Verbatim:
                    self.text_buffer.append('\\')

            case InlineLeaf.HARD_BREAK:
                # '\\n'
                if self.context == Context.Normal:
                    self._add_child_to_tip(HardBreak(
                        pos=pos
                    ))
                else:
                    self.text_buffer.append('\n')
            case InlineLeaf.NBSP:
                # '\ '
                if self.context == Context.Verbatim:
                    self.text_buffer.append('\\ ')
                else:
                    self._add_child_to_tip(NonBreakingSpace(
                        pos=pos,
                    ))
            case InlineLeaf.SYMBOL:
                # :symbol:
                if self.context == Context.Normal:
                    alias = self.src[event.startpos+1:event.endpos] # between :
                    self._add_child_to_tip(Symb(
                        pos=pos,
                        alias=alias,
                    ))
                else:
                    self.text_buffer.append(text_content)
            case InlineLeaf.FOOTNOTE_REF:
                # [^foo]
                fn_ref = self.src[event.startpos+2:event.endpos]
                self._add_child_to_tip(FootnoteReference(
                    pos=pos,
                    text=normalize_label(fn_ref)
                ))
            case InlineLeaf.REFERENCE_KEY:
                self.stack[-1].set_ref_key(self.src[event.startpos+1:event.endpos]) # content inside brackets.
            case InlineLeaf.REFERENCE_VALUE:
                self.stack[-1].set_ref_val(self.src[event.startpos:event.endpos+1])
            case InlineLeaf.RAW_FORMAT:
                self._attach_raw_format(text_content)
            case _:
                pass

    def _attach_raw_format(self, format: str):
        format = normalize_raw_format(format)
        frame = self.stack[-1]
        if self.context == Context.Verbatim:
            frame.format = format
        else:
            last_node = frame.children[-1]
            if isinstance(last_node, Verbatim):
                raw_inline = RawInline(
                    attributes=last_node.attributes,
                    pos=last_node.pos,
                    format=format,
                    text=last_node.text,
                )
                frame.children[-1] = raw_inline
            else:
                raise Exception('raw_format is not after verbatim or code_block')

    def _process_attr_leaf(self, kind: AttrKind, text: str):
        if not self.stack:
            return
        
        top = self.stack[-1]
        match kind:
            case AttrKind.CLASS:
                top.set_class(text)
            case AttrKind.ID:
                top.set_id(text)
            case AttrKind.KEY:
                top.set_attr_key(text)
            case AttrKind.VALUE:
                top.set_attr_val(text)


    def _add_child_to_tip(self, child: AstNode):
        if self.stack:
            self.stack[-1].add_child(child)

    def _calc_pos(self, start: int, end: int) -> Pos:
        """根据字符偏移量生成 ast.py 中的 SourceLoc / Pos 对象"""
        start_loc = get_source_loc(self.line_starts, start)
        end_loc = get_source_loc(self.line_starts, end)
        return Pos(
            start=start_loc,
            end=end_loc,
        )

