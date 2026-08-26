from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Dict, List

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
)

@dataclass
class Container:
    children: List[Any]
    attributes: Attributes | None
    auto_attributes: Attributes | None
    data: Dict[str, Any]
    pos: Pos | None

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

    def add_block_attributes(self, container: HasAttributes):
        if len(self.block_attributes) > 0:
            container.attributes = container.attributes or {}
            for k, v in self.block_attributes.items():
                container.attributes[k] = v
                del self.block_attributes[k]

    
