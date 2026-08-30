from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import re
from typing import Any, Callable, Dict, List, Optional, Set

from .event import Event
from .block import parse_events
from .options import (
    Options,
    Warning,
)
from .ast import (
    Attributes,
    SourceLoc,
    Pos,
    HasAttributes,
    HasText,
    HasChildren,
    SoftBreak,
    HardBreak,
    ThematicBreak,
    Term,
    Definition,
    AstNode,
    Doc,
    Reference,
    Footnote,
    FootnoteReference,
    is_row,
    is_block,
    is_caption,
    is_inline,
    Caption,
    Str,
    NonBreakingSpace,
    Symb,
    FootnoteReference,
    Reference,
    Emph,
    Strong,
    Span,
    Mark,
    Superscript,
    Subscript,
    Delete,
    Insert,
    DoubleQuoted,
    SingleQuoted,
    Attributes,
    Image,
    Link,
    Reference,
    Verbatim,
    RawInline,
    DisplayMath,
    InlineMath,
    Url,
    Email,
    Para,
    Section,
    Heading,
    DefinitionList,
    TaskList,
    BulletList,
    BulletListStyle,
    OrderedList,
    OrderedListStyle,
    Section,
)

@dataclass
class Container(HasAttributes):
    data: Dict[str, Any]
    children: List[Any]


def get_string_content(node: AstNode | Container) -> str:
    buf: List[str] = []
    add_string_content(node, buf)
    return ''.join(buf)

def add_string_content(node: AstNode | Container, buf: List[str]):
    if isinstance(node, FootnoteReference):
        return
    
    if isinstance(node, HasText):
        buf.append(node.text)
    elif isinstance(node, (SoftBreak, HardBreak)):
        buf.append('\n')
    elif isinstance(node, HasChildren):
        for child in node.children:
            add_string_content(child, buf)

patt_verbatim_start = re.compile(r'^ `')
patt_verbatim_end = re.compile(r'` $')

def trim_verbatim(text: str) -> str:
    text = patt_verbatim_start.sub('`', text)
    text = patt_verbatim_end.sub('`', text)
    return text

roman_digits = {
    'i': 1,
    'v': 5,
    'x': 10,
    'l': 50,
    'c': 100,
    'd': 500,
    'm': 1000,
    'I': 1,
    'V': 5,
    'X': 10,
    'L': 50,
    'C': 100,
    'D': 500,
    'M': 1000,
}

def roman_to_number(s: str) -> int:
    total = 0
    prevdigit = 0
    i = len(s) - 1
    while i >= 0:
        c = s[i]
        if c not in roman_digits:
            raise ValueError(f'Encountered bad character in roman numeral {s}')
        n = roman_digits[c]
        if n < prevdigit: # e.g. ix
            total -= n
        else:
            total += n
        prevdigit = n
        i -= 1

    return total

patt_paren_dot = re.compile(r'[().]')

def get_list_start(marker: str, style: str) -> int | None:
    numtype = patt_paren_dot.sub('', style)
    s = patt_paren_dot.sub('', marker)

    match numtype:
        case '1':
            return int(s)
        case 'A':
            return ord(s[0]) - 65 + 1 # 65 = 'A'
        case 'a':
            return ord(s[0]) - 97 + 1
        case 'I':
            return roman_to_number(s)
        case 'i':
            return roman_to_number(s)
        case _:
            return None

@dataclass
class ParseOptions(Options):
    source_positions: bool

class Context(Enum):
    Normal = 0
    Verbatim = 1
    Literal = 2

patt_whitespace = re.compile(r'[ \t\r\n]+')

def normalize_label(label: str) -> str:
    return patt_whitespace.sub(' ', label.strip())

def get_line_starts(text: str) -> List[int]:
    """获取字符串中所有换行符的位置（包括起始位置 -1）
    
    Args:
        text: 输入文本
        
    Returns:
        换行符位置列表，第一个元素为 -1
        
    Examples:
        >>> get_line_starts("hello\nworld\n")
        [-1, 5, 11]
    """
    starts = [-1]
    # Or an approach to avoid python loop:
    # pos = -1
    # while True:
    #     pos = text.find('\n', pos + 1)
    #     if pos == -1:
    #         break
    #     starts.append(pos)
    for i, char in enumerate(text):
        if char == '\n':
            starts.append(i)
    return starts

def get_source_loc(linestarts: List[int], pos: int) -> SourceLoc:
    numlines = len(linestarts)
    bottom = 0
    top = numlines - 1
    line = 0
    col = 0
    while not line:
        mid = bottom + (top - bottom) // 2
        if linestarts[mid] > pos: # lower part
            top = mid
        elif linestarts[mid] <= pos:
            # Reaching the last line, or pos is within mid line and mid+1 line.
            if mid == top or linestarts[mid + 1] > pos:
                line = mid + 1
                col = pos - linestarts[mid]
            else:
                if bottom == mid and bottom < top:
                    bottom = mid + 1
                else:
                    bottom = mid

    return SourceLoc(line, col, pos)

class UniqiueIdentifierGenerator:

    _INVALID_CHARS = re.compile(r'[\]\[~!@#$%^&*(){}`,.<>\\|=+/?\s]+')
    _MULTIPLE_SPACES = re.compile(r' +')
    
    def __init__(self):
        self.identifiers = set()

    def generate(self, s: str) -> str:
        # 转换为小写（通常 ID 是小写）
        s = s.lower()
        
        # 清理文本
        slug = self._clean_text(s)
        
        # 确保唯一性
        return self._ensure_unique(slug)
    
    def _clean_text(self, text: str) -> str:
        """清理文本，生成基础 slug"""
        # 特殊字符转空格
        cleaned = self._INVALID_CHARS.sub(' ', text)
        # 去除首尾空格
        cleaned = cleaned.strip()
        # 多个空格转连字符
        return self._MULTIPLE_SPACES.sub('-', cleaned)
    
    def _ensure_unique(self, base: str) -> str:
        """确保标识符唯一"""
        if not base:
            base = 's'
        
        counter = 0
        slug = base
        
        while slug in self.identifiers:
            counter += 1
            slug = f"{base}-{counter}"
        
        self.identifiers.add(slug)
        return slug

HandlerFn = Callable[[List[str], int, int, Optional[Pos]]]

class Parser:
    """
    Modified from parseFromEvents
    """
    def __init__(
        self, 
        events: List[Event],
        input_: str,
        options: ParseOptions
    ):
        self.events = events
        self.input = input_
        self.options = options

        self.linestarts: List[int] = [-1]

        if self.options.source_positions:
            self.linstarts = get_line_starts(self.input)

        self.context = Context.Normal
        self.accumulated_text = ''
        self.references: Dict[str, Reference] = {}
        self.auto_references: Dict[str, Reference] = {}
        self.footnotes: Dict[str, Footnote] = {}
        self.identifiers: Dict[str, bool] = {} # identifiers usd.
        self.id_generator = UniqiueIdentifierGenerator()
        self.block_attributes: Attributes = {} # accumulatd block attributes
        self.list_depth = 0

        self.containers: List[Container] = [
            # root container is a placeholder
            Container(
                attributes=None,
                auto_attributes=None,
                data={
                    'heading_level': 0,
                },
                pos=Pos(
                    start=SourceLoc(line=0, col=0, offset=0),
                    end=SourceLoc(line=0, col=0, offset=0),
                ),
                children=[],
            )
        ]

        self.handlers: Dict[str, HandlerFn] = {
            'str': self.handle_str,
            'soft_break': self.handle_soft_break,
            'escape': self.handle_escape,
            'hard_break': self.handle_hard_break,
            'non_breaking_space': self.handle_non_breaking_space,
        }

        

    def add_block_attributes(self, container: HasAttributes):
        """
        Transfer block attributes to container.
        """
        if len(self.block_attributes) > 0:
            container.attributes = container.attributes or {}
            for k, v in self.block_attributes.items():
                container.attributes[k] = v
                del self.block_attributes[k]

    def push_container(self, pos: Pos | None = None):
        container = Container(
            attributes=None,
            auto_attributes=None,
            data={},
            pos=pos,
            children=[],
        )
        self.add_block_attributes(container)
        self.containers.append(container)

    def pop_container(self, pos: Pos | None = None) -> Container:
        node = self.containers.pop()
        if pos and node.pos:
            node.pos = Pos(
                start=node.pos.start,
                end=pos.end,
            )

        return node

    def top_container(self) -> Container:
        return self.containers[-1]

    def get_tip(self) -> Container | AstNode:
        top = self.top_container()
        if top.children:
            return top.children[-1]
        else:
            return top

    def add_child_to_tip(self, child: AstNode):
        if self.containers:
            tip = self.containers[-1]
            tip.children.append(child)

    def handle_str(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        txt = self.input[startpos:endpos+1]
        if self.context == Context.Normal:
            self.add_child_to_tip(Str(
                attributes=None,
                auto_attributes=None,
                pos=pos,
                text=txt
            ))
        else:
            self.accumulated_text += txt

    def handle_soft_break(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        if self.context == Context.Normal:
            self.add_child_to_tip(SoftBreak(
                attributes=None,
                auto_attributes=None,
                pos=pos,
            ))
        else:
            self.accumulated_text += '\n'

    def handle_escape(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        if self.context == Context.Verbatim:
            self.accumulated_text += '\\'

    def handle_hard_break(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        if self.context == Context.Normal:
            self.add_child_to_tip(HardBreak(
                attributes=None,
                auto_attributes=None,
                pos=pos,
            ))
        else:
            self.accumulated_text += '\n'

    def handle_non_breaking_space(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        if self.context == Context.Verbatim:
            self.accumulated_text += '\\ '
        else:
            self.add_child_to_tip(NonBreakingSpace(
                attributes=None,
                auto_attributes=None,
                pos=pos,
            ))

    def handle_symb(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        if self.context == Context.Normal:
            alias = self.input[startpos+1:endpos+1]
            self.add_child_to_tip(Symb(
                attributes=None,
                auto_attributes=None,
                pos=pos,
                alias=alias,
            ))
        else:
            txt = self.input[startpos:endpos+1]
            self.accumulated_text += txt

    def handle_footnote_reference(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        fnref = self.input[startpos+2:endpos+1]
        self.add_child_to_tip(FootnoteReference(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            text=normalize_label(fnref)
        ))

    def handle_plus_reference_definition(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_minus_reference_definition(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        lab = normalize_label(node.data.get('key', ''))
        r = Reference(
            attributes=node.attributes,
            auto_attributes=None,
            pos=pos,
            label=lab,
            destination=node.data.get('value', ''),
        )
        if 'key' in node.data:
            self.references[lab] = r

    def handle_reference_key(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.top_container().data['key'] = self.input[startpos+1:endpos]
        self.top_container().data['value'] = ''

    def handle_reference_value(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.top_container().data['value'] = self.top_container().data['value'] + self.input[startpos:endpos+1]

    def handle_plus_emph(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_minus_emph(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Emph(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_plus_strong(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_minus_strong(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Strong(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_plus_span(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_minus_span(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Span(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))
    
    def handle_open_mark(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_mark(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Mark(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_open_superscript(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_superscript(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Superscript(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_open_subscript(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_subscript(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Subscript(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_open_delete(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_delete(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Delete(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_open_insert(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_insert(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Insert(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_open_double_quoted(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_double_quoted(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(DoubleQuoted(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_open_single_quoted(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_single_quoted(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(SingleQuoted(
            attributes=None,
            auto_attributes=None,
            pos=pos,
            children=node.children,
        ))

    def handle_open_attributes(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_attributes(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        if node.attributes and self.containers:
            if 'id' in node.attributes:
                self.identifiers[node.attributes['id']] = True

            tip = self.get_tip()
            if tip == self.top_container():
                return

            ends_with_space = False
            if isinstance(tip, Str): # bare word
                m = re.search(r'[^\s]+$', tip.text)
                if m and m.start() > 0:
                    wordpos: Pos | None = None
                    if tip.pos:
                        origend = tip.pos.end
                        tip.pos.end = SourceLoc(
                            line=origend.line,
                            col=origend.col - (m.end() - m.start()),
                            offset=origend.offset - (m.end() - m.start()),
                        )
                        wordpos = Pos(
                            start=SourceLoc(
                                line=origend.line,
                                col=origend.col - (m.end() - m.start()) + 1,
                                offset=origend.offset - (m.end() - m.start()) + 1,
                            ),
                            end=tip.pos.end,
                        )
                    tip.text = tip.text[:m.start()]
                    self.add_child_to_tip(Str(
                        attributes=None,
                        auto_attributes=None,
                        pos=wordpos,
                        text=tip.text,
                    ))
                elif not m:
                    ends_with_space = True

            tip = self.get_tip()
            if ends_with_space:
                self.options.warn(Warning(
                    message='Ignoring unattached attribute',
                    pos=get_source_loc(self.linestarts, startpos) if self.options.source_positions else startpos
                ))
                return

            if isinstance(tip, HasAttributes):
                if not tip.attributes:
                    tip.attributes = {}

                for key, value in node.attributes.items():
                    if key == 'class':
                        if key in tip.attributes:
                            tip.attributes[key] += ' ' + value
                        else:
                            tip.attributes[key] = value
                    else:
                        tip.attributes[key] = value

    def handle_open_block_attributes(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_block_attributes(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        if node.attributes and self.containers:
            if 'id' in node.attributes:
                self.identifiers[node.attributes['id']] = True
            for k, v in node.attributes.items():
                if k == 'class':
                    if k in self.block_attributes:
                        self.block_attributes[k] = self.block_attributes[k] + ' ' + v
                    else:
                        self.block_attributes[k] = v
                else:
                    self.block_attributes[k] = v

    def handle_class(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        top = self.top_container()
        cl = self.input[startpos:endpos+1]
        if not top.attributes:
            top.attributes = {}

        if 'class' in top.attributes:
            top.attributes['class'] += ' ' + cl
        else:
            top.attributes['class'] = cl

    def handle_id(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        top = self.top_container()
        id_ = self.input[startpos:endpos+1]
        if not top.attributes:
            top.attributes = {'id': id_}
        else:
            top.attributes['id'] = id_

    def handle_key(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        top = self.top_container()
        key = self.input[startpos:endpos+1]
        top.data['key'] = key
        if not top.attributes:
            top.attributes = {}

        top.attributes[top.data[key]] = ''
        # What's the difference from top.attributes[key] = ''?

    def handle_value(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        top = self.top_container()
        val = self.input[startpos:endpos+1]
        val = re.sub(r'[ \r\n]+', ' ', val)
        # 去除特定标点符号前面的反斜杠（即“反转义”）
        # 在 Python 中，如果捕获组里的内容不需要做额外处理，只是原样放回，我们完全不需要捕获组，可以使用零宽断言（Lookahead）
        val = re.sub(r'\\(?=[.,\\/#!$%^&*;:{}=\-_`~+[\]()\'"?|])', '', val)

        # resolve backslash escapes
        if not top.attributes:
            top.attributes = {}

        if 'key' in top.data:
            top.attributes[top.data['key']] = top.attributes[top.data['key']] + val
        else:
            raise Exception('Encountered value without key')

    def handle_open_linktext(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)
        self.top_container().data['isimage'] = False

    def handle_close_linktext(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        pass

    def handle_open_imagetext(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)
        self.top_container().data['isimage'] = True

    def handle_close_imagetext(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        pass

    def handle_open_destination(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.context = Context.Literal

    def handle_close_destination(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        if node.data['isimage']:
            child = Image(
                attributes=node.attributes,
                auto_attributes=node.auto_attributes,
                pos=node.pos,
                children=node.children,
                destination=self.accumulated_text,
                reference=None,
            )
        else:
            child = Link(
                attributes=node.attributes,
                auto_attributes=node.auto_attributes,
                pos=node.pos,
                children=node.children,
                destination=self.accumulated_text,
                reference=None,
            )
        self.add_child_to_tip(child)

        self.context = Context.Normal
        self.accumulated_text = ''

    def handle_open_reference(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.context = Context.Literal

    def handle_close_reference(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        ref = self.accumulated_text
        if not ref:
            ref = get_string_content(node)

        if node.data['isimage']:
            child = Image(
                attributes=node.attributes,
                auto_attributes=node.auto_attributes,
                pos=node.pos,
                children=node.children,
                destination=None,
                reference=normalize_label(ref),
            )
        else:
            child = Link(
                attributes=node.attributes,
                auto_attributes=node.auto_attributes,
                pos=node.pos,
                children=node.children,
                destination=None,
                reference=normalize_label(ref),
            )
        self.add_child_to_tip(child)
        self.context = Context.Normal
        self.accumulated_text = ''

    def handle_open_verbatim(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.context = Context.Verbatim
        self.push_container(pos)

    def handle_close_verbatim(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Verbatim(
            attributes=node.attributes,
            auto_attributes=node.auto_attributes,
            pos=node.pos,
            text=self.accumulated_text,
        ))

        self.context = Context.Normal
        self.accumulated_text = ''

    def handle_raw_format(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        format = self.input[startpos:endpos+1]
        # ^：匹配字符串的开头。
        # \{?=：匹配一个可选的 {，后面紧跟一个 =。
        # \}$：匹配字符串结尾的 }。
        # 作用：如果字符串以 } 结尾，就把它删掉。
        format = re.sub(r'^\{?=|\}$', '', format)
        top = self.top_container()
        if self.context == Context.Verbatim:
            top.data['format'] = format
        else:
            # Raw inline:
            # `<?php echo 'hello world!' ?>`{=html}
            # Code block:
            # ```ruby
            # x = 5 * 6
            # ```
            tip = top.children[-1]
            if isinstance(tip, Verbatim):
                raw_inline = RawInline(
                    attributes=tip.attributes,
                    auto_attributes=tip.auto_attributes,
                    pos=tip.pos,
                    format=format,
                    text=tip.text,
                )
                top.children[-1] = raw_inline
            else:
                raise Exception('raw_format is not after verbatim or code_block')

    def handle_open_display_math(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.context = Context.Verbatim
        self.push_container(pos)

    def handle_open_inline_math(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.context = Context.Verbatim
        self.push_container(pos)

    def handle_close_display_math(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(DisplayMath(
            attributes=node.attributes,
            auto_attributes=node.auto_attributes,
            pos=node.pos,
            text=trim_verbatim(self.accumulated_text),
        ))

        self.context = Context.Normal
        self.accumulated_text = ''

    def handle_close_inline_math(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(InlineMath(
            attributes=node.attributes,
            auto_attributes=node.auto_attributes,
            pos=node.pos,
            text=trim_verbatim(self.accumulated_text),
        ))
        self.context = Context.Normal
        self.accumulated_text = ''
    

    def handle_open_url(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.context = Context.Literal
        self.push_container(pos)

    def handle_close_url(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Url(
            attributes=node.attributes,
            auto_attributes=node.auto_attributes,
            pos=node.pos,
            text=re.sub(r'[\r\n]', '', self.accumulated_text),
        ))
        self.context = Context.Normal
        self.accumulated_text = ''

    def handle_open_email(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.context = Context.Literal
        self.push_container(pos)

    def handle_close_email(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Email(
            attributes=node.attributes,
            auto_attributes=node.auto_attributes,
            pos=node.pos,
            text=re.sub(r'[\r\n]', '', self.accumulated_text),
        ))

    def handle_open_para(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)

    def handle_close_para(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        self.add_child_to_tip(Para(
            attributes=node.attributes,
            auto_attributes=node.auto_attributes,
            pos=node.pos,
            children=node.children,
        ))

    def handle_open_heading(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)
        self.top_container().data['level'] = 1 + endpos - startpos

    def handle_close_heading(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        heading_str = get_string_content(node).strip()

        if not node.attributes or 'id' not in node.attributes:
            # TODO: what is auto attributes?
            if not node.auto_attributes:
                node.auto_attributes = {}
            node.auto_attributes['id'] = self.id_generator.generate(heading_str)
            self.identifiers[node.auto_attributes['id']] = True

        lab = normalize_label(heading_str)
        if lab not in self.references and lab not in self.auto_references:
            id_ = node.attributes.get('id', '') if node.attributes else ''
            if not id_:
                id_ = node.auto_attributes.get('id', '') if node.auto_attributes else ''

            self.auto_references[lab] = Reference(
                attributes=None,
                auto_attributes=None,
                pos=None,
                label=lab,
                destination='#' + id_,
            )

        pnode = self.top_container()
        if 'headinglevel' in pnode.data:
            while pnode and 'headinglevel' in pnode.data and pnode.data['headinglevel'] > node.data['level']:
                pnode = self.pop_container(pos)

                self.add_child_to_tip(Section(
                    attributes=pnode.attributes,
                    auto_attributes=pnode.auto_attributes,
                    pos=pnode.pos,
                    children=pnode.children,
                ))

            self.push_container(node.pos)
            self.top_container().data['headinglevel'] = node.data['level']
            # move id attribute from heading to section
            if node.auto_attributes and node.auto_attributes['id']:
                self.top_container().auto_attributes = node.auto_attributes
                # TODO: why?
                del node.auto_attributes

            if node.attributes and node.attributes['id']:
                self.top_container().attributes = node.attributes
                # TODO: why?
                del node.attributes

        self.add_child_to_tip(Heading(
            attributes=node.attributes,
            auto_attributes=node.auto_attributes,
            pos=node.pos,
            level=node.data['level'],
            children=node.children,
        ))

    def handle_open_list(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        self.push_container(pos)
        self.top_container().data['style'] = suffixes
        self.top_container().data['blanklines'] = False
        self.top_container().data['tight'] = True
        self.list_depth += 1

    def handle_close_list(self, suffixes: List[str], startpos: int, endpos: int, pos: Pos | None = None):
        node = self.pop_container(pos)
        list_style: str = node.data['style'][0]
        if not list_style:
            raise Exception('No style defined for list')

        list_start = get_list_start(node.data['first_marker'], list_style)
        if list_style == ':':
            self.add_child_to_tip(DefinitionList(
                attributes=node.attributes,
                auto_attributes=node.auto_attributes,
                pos=node.pos,
                children=node.children,
            ))
        elif list_style.endswith('X'):
            self.add_child_to_tip(TaskList(
                attributes=node.attributes,
                auto_attributes=node.auto_attributes,
                pos=node.pos,
                children=node.children,
                tight=node.data['tight'],
            ))
        elif list_style == '+' or list_style == '*' or list_style == '-':
            self.add_child_to_tip(BulletList(
                attributes=node.attributes,
                auto_attributes=node.auto_attributes,
                pos=node.pos,
                children=node.children,
                tight=node.data['tight'],
                style=BulletListStyle(list_style),
            ))
        else:
            self.add_child_to_tip(OrderedList(
                attributes=node.attributes,
                auto_attributes=node.auto_attributes,
                pos=node.pos,
                children=node.children,
                tight=node.data['tight'],
                style=OrderedListStyle(list_style),
                start=list_start,
            ))

        self.list_depth -= 1

    def handle_event(self, containers: List[Container], event: Event):
        pos = None
        if self.options.source_positions:
            sp = get_source_loc(self.linestarts, event.startpos)
            ep = get_source_loc(self.linestarts, event.endpos)
            pos = Pos(
                start=sp,
                end=ep,
            )

        annot = event.annot
        suffixes: List[str] = []
        # TODO: what is this?
        if '|' in event.annot:
            parts = event.annot.split('|')
            annot = parts[0]
            suffixes = parts[1:]

        # Attributes must come right before a block, so we
        # reset them on blank lines.
        if annot == 'blankline':
            for k in self.block_attributes:
                del self.block_attributes[k]

        # The following is for tight/loose determination.
        # If blanklines have already been seen, and we're
        # about to process something other than a blankline,
        # the end of a list or list item, or the start of
        # a list, then it's a loose list.
        if self.list_depth > 0 and annot != 'blankline':
            top = self.top_container()
            ln = None
            if top:
                if top.data and 'tight' in top.data:
                    ln = top
                elif len(self.containers) >= 2 and 'tight' in self.containers[-2].data:
                    ln = self.containers[-2]

            if ln:
                if re.match(r'^[+-]list', annot) and ln.data['blanklines']:
                    ln.data['tight'] = False
                if re.match(r'^[-+]list_item', annot) or re.match(r'^[0-9]+list', annot):
                    ln.data['blanklines'] = False

        if annot in self.handlers:
            fn = self.handlers[annot]
            fn(suffixes, event.startpos, event.endpos, pos)

    def parse_from_events(self):
        lastpos = 0
        for event in self.events:
            self.handle_event(self.containers, event)
            lastpos = event.endpos

        lastloc = None
        if self.options.source_positions:
            lastloc = get_source_loc(self.linestarts, lastpos)

        pnode = self.top_container()
        while pnode and pnode.data['headinglevel'] > 0:
            self.pop_container(Pos(start=lastloc, end=lastloc) if lastloc else None)
            self.add_child_to_tip(Section(
                attributes=None,
                auto_attributes=None,
                pos=pnode.pos,
                children=pnode.children,
            ))
            pnode = self.top_container()

        doc = Doc(
            attributes=None,
            auto_attributes=None,
            pos=None,
            references=self.references,
            auto_references=self.auto_references,
            footnotes=self.footnotes,
            children=self.containers[0].children,
        )
        if self.containers[0].auto_attributes:
            doc.auto_attributes = self.containers[0].auto_attributes
        if self.containers[0].attributes:
            doc.attributes = self.containers[0].attributes

        return doc

OMIT_FIELDS: Set[str] = {
    'children',
    'tag',
    'pos',
    'attributes'
    'auto_attributes',
    'references',
    'auto_references',
    'footnotes',
}

import json

def stringify(x: object) -> str:
    # 转为 JSON 字符串
    json_str = json.dumps(x, ensure_ascii=False)
    
    # 如果 JSON 字符串中真的出现了“反斜杠+真实换行符”的组合，
    # 把它替换为“反斜杠+字母n”（即 \n 的字面量）
    return json_str.replace("\\\n", "\\n")

def render_ast_node(
        node: AstNode, 
        buff: List[str],
        indent: int
    ):
    buff.append(' ' * indent)
    if indent > 128:
        buff.append("(((DEEPLY NESTED CONTENT OMITTED)))\n")
        return

    buff.append(node.tag)
    if isinstance(node, HasAttributes):
        if node.pos:
            buff.append(f' ({node.pos.start.line}:{node.pos.start.col}:{node.pos.start.offset}-{node.pos.end.line}:{node.pos.end.col}:{node.pos.end.offset})')

    if is_dataclass(node):
        for field in fields(node):
            if field.name not in OMIT_FIELDS:
                v = getattr(node, field.name)
                if v is not None:
                    buff.append(f' {field.name}={stringify(v)}')

    if isinstance(node, HasAttributes) and node.attributes:
        for k, v in node.attributes.items():
            buff.append(f' {k}={stringify(v)}')

    buff.append('\n')
    if isinstance(node, HasChildren) and node.children:
        for child in node.children:
            render_ast_node(child, buff, indent + 2)

def render_ast(doc: Doc) -> str:
    """
    Render an AST in human-readable form, with indentation
    showing the hierarchy.
    """
    buff: List[str] = []
    render_ast_node(doc, buff, 0)
    if len(doc.references) > 0:
        buff.append('references\n')
        for k, v in doc.references.items():
            buff.append(f'  [{stringify(k)}] =\n')
            render_ast_node(v, buff, 4)

    if len(doc.footnotes) > 0:
        buff.append('footnotes\n')
        for k, v in doc.footnotes.items():
            buff.append(f'  [{stringify(k)}] =\n')
            render_ast_node(v, buff, 4)

    return ''.join(buff)

def parse(input_: str, options: ParseOptions | None = None) -> Doc:
    if options is None:
        options = ParseOptions(source_positions=False)
    parser = parse_events(input_, options)
    return Parser(list(parser), input_, options).parse_from_events()