from dataclasses import dataclass
import re
from typing import List, Optional

from .common import Range

@dataclass(slots=True, frozen=True)
class MatchedRange:
    start: int
    end: int
    captures: List[str]
    
# The TS version `find` is is a hack of JS regular expression,
# which is already implemented by Python re.Pattern.search.
def find(
    subject: str, 
    patt: re.Pattern, 
    startpos: int, 
    endpos: int | None = None
) -> MatchedRange | None:
    """
    In djot.js, the find function is implemented by JS regular expression.

    It first creates new RegExp(patt, 'yd'), which means that match must start at the RegExp.lastIndex property.
    When you can `find`, it will set `patt.lastIndex = startpos` to enfore a `^` behavior.
    In Python, it is equivalent to `match` rather than `search`.
    """
    if endpos is not None:
        m = patt.match(subject, startpos, endpos + 1)
    else:
        m = patt.match(subject, startpos)

    if m:
        return MatchedRange(
            start=m.start(), # start of whole match.
            end=m.end()-1, # the last char of whole match.
            captures=list(m.groups()) # Match.groups() returns a tuple containing string or None.
        )

class InputText:
    _PATT_BANGS = re.compile(r'#+')
    _PATT_WHITESPACE = re.compile(r'[ \t\r\n]')
    _PATT_BLOCKQUOTE_PREFIX = re.compile(r'[>][ \t\r\n]')
    _PATT_CAPTION_START = re.compile(r'\^[ \t]+')
    _PATT_FOOTNOTE_START = re.compile(r'\[\^([^\]]+)\]:[ \t\r\n]')
    _PATT_REFERENCE_DEFINITION = re.compile(r'\[([^\]\r\n]*)\]:([ \t]+[^ \t\r\n]*|)[\r\n]')
    _PATT_THEMATIC_BREAK = re.compile(r'[-*][ \t]*[-*][ \t]*[-*][-* \t]*\r?\n')
    _PATT_LIST_MARKER = re.compile(
        r'(:?[-*+:]' # - or * or + or :
        r'|\([0-9]+\)' # (1)
        r'|[0-9]+[.)]' #  1. or 1)
        r'|[ivxlcdmIVXLCDM]+[.)]' # i. or i)
        r'|\([ivxlcdmIVXLCDM]+\)' # (i)
        r'|[a-zA-Z][.)]' # a. or a) or A. or A)
        r'|\([a-zA-Z]\)' # (a) or (A)
        r')'
        r'[ \t\r\n]'
    )
    _PATT_TASK_LIST_MARKER = re.compile(
        r'[*+-] \[[Xx ]\][ \t\r\n]' # - [ ] or - [X]
    )
    # Match the whole line:
    # A pipe, followed by anything but new line, ended with a pipe.
    _PATT_TABLE_ROW = re.compile(r'(\|[^\r\n]*\|)[ \t]*\r?\n')
    # Match optional :, followed by at least one or more -,
    # followed by optional :, followed by optinal space/tab,
    # followed by pipe, followed by optional space.
    _PATT_ROW_SEP = re.compile(r'(:?)--*(:?)([ \t]*\|[ \t]*)')
    _PATT_NEXT_BAR_OR_TICK = re.compile(r'[^`|\r\n]*(?:[|]|`+)')
    _PATT_WORD = re.compile(r'\w+\s')
    
    _PATT_DIV_FENCE_START = re.compile(r'(::::*)[ \t]*')
    _PATT_DIV_FENCE_END = re.compile(r'([\w_-]*)[ \t]*\r?\n')
    _PATT_DIV_FENCE = re.compile(r'(::::*)[ \t]*\r?\n')
    _PATT_CODE_FENCE = re.compile(r'(~~~~*|````*)([ \t]*)([^ \t\r\n`]*)[ \t]*\r?\n')

    # Inline
    _RE_SPECIAL = re.compile(
        r'''[\r\n"'()*+.:<=\[\\\]^_`${}~-]'''
    )
    # {=FORMAT}
    _PATT_RAW_ATTRIBUTE = re.compile(r'\{=[^\s{}`]+\}')
    _PATT_BACKTICKS0 = re.compile(r'`*')
    _PATT_BACKTICKS1 = re.compile(r'`+')
    _PATT_DOUBLE_DOLLARS = re.compile(r'\$\$')
    _PATT_SINGLE_DOLLAR = re.compile(r'\$')
    _PATT_BACKSLASH = re.compile(r'\\')
    _PATT_PUNCTUATION = re.compile(
        r'''['!"#%&\\'()*+,\-./:;<=>?@\[\]^`{|}~']'''
    )
    # <https://pandoc.org/lua-filters>
    # <me@example.com>
    _PATT_AUTOLINK = re.compile(r'<([^<>\s]+)>')
    _PATT_DELIM = re.compile(r'''[_*~^+='"-]''')
    _PATT_SYMBOL = re.compile(r':[\w_+-]+:')
    _PATT_TWO_PERIODS = re.compile(r'\.\.')
    _PATT_NOTE_REFERENCE = re.compile(r'\^([^\]]+)\]')

    # Replace `const pattNonspace = pattern("[^ \t\r\n]")` in djot.js.
    # When you want to determine if a single char is space,
    # use short plain str is always optimal in Python.
    _WHITESPACE = ' \t\r\n'
    _SPACE_TAB = ' \t'
    _CR_LF = '\r\n'
    
    def __init__(self, src: str) -> None:
        if src and src[-1] != '\n':
            src += '\n'
        self.src = src
        self.pos = 0
        self.length = len(src)

        # Current line context
        self.indent = 0
        self.line_start = 0
        self.eol_start = 0 # start of newline char
        self.eol_end = 0 # end of newline char

    @property
    def maxoffset(self) -> int:
        return self.length - 1

    @property
    def is_blank_line(self) -> bool:
        return self.pos == self.eol_start

    def is_eof(self) -> bool:
        return self.pos >= self.length

    def is_eol(self) -> bool:
        return self.pos == self.eol_start

    def is_eol_at(self, i: int) -> bool:
        """
        Check if char at i is newline or return char.
        """
        if i >= self.length:
            return False

        return self.src[i] in '\r\n'

    def _calculate_eol(self):
        i = self.pos
        while not self.is_eol_at(i):
            i += 1

        self.eol_start = i
        # \r\n
        if self.is_crlf(i):
            self.eol_end = i + 1
        else: # \n
            self.eol_end = i

    def start_newline(self):
        """
        初始化当前行的行首上下文（Reset Line Context）
        在处理每一行前，清空上一行的临时状态，并确立当前行的物理边界。
        """
        self.indent = 0 # 重置当前行的缩进计数（用于计算空格/Tab）
        self.line_start = self.pos # 标记当前行的起始字符绝对位置（Cursor Offset）
        self._calculate_eol() # 预先扫描并定位当前行的行尾（\n 或 \r\n）位置

    def advance_to_new_line(self):
        self.pos = (self.eol_end or self.pos) + 1
    
    def advance(self, n: int = 1):
        """Move cursor by n steps
        
        Args:
            n: The number to steps to move. Default to 1
        """
        self.pos += n
    
    def advance_to(self, newpos: int):
        self.pos = newpos

    def advance_to_eol(self):
        self.pos = self.eol_start

    def get_adjusted_text_start(self, indent: Optional[int]) -> int:
        if indent is None:
            return self.pos
        if self.indent <= indent:
            return self.pos

        return self.pos - (self.indent - indent) # does this amount to indent itself?


    def skip_space(self):
        """
        跳过当前行的前导空格，并更新 self.indent
        """
        newpos = self.pos

        while newpos < self.length and self.src[newpos] in self._SPACE_TAB:
            newpos += 1

        self.indent = newpos - self.line_start
        self.pos = newpos

    def new_span(self, start: int, end: int) -> Range:
        return Range(
            start=min(start, self.maxoffset),
            end=min(end, self.maxoffset)
        )

    def current_span(self) -> Range:
        """Create a Range at curent position"""
        return Range(
            start=min(self.pos, self.maxoffset),
            end=min(self.pos, self.maxoffset)
        )

    def rest_line_span(self) -> Range:
        """Create a Range from current position to end of line."""
        return Range(
            start=min(self.pos, self.maxoffset),
            end=min(self.eol_end, self.maxoffset)
        )
    
    def char_at(self, i: int) -> Optional[str]:
        if i >= self.length:
            return None

        return self.src[i]

    def peek_char_is(self, ch: str) -> bool:
        if self.pos >= self.length or self.pos < 0:
            return False
        
        return self.src[self.pos] == ch

    def is_rest_of_line_blank(self, start: int) -> bool:
        while start < self.length:
            c = self.src[start]
            if c in self._SPACE_TAB:
                start += 1
            elif c in self._CR_LF:
                return True
            else:
                return False # non-space

        return False # EOF without newline.

    def find_rest_of_line_blank_end(self, pos: int, endpos: int) -> Optional[int]:
        """
        从 pos 位置开始扫描，如果直到行尾（包含 \n 或 \r\n）只有空格或制表符，
        返回换行符结束的字符索引 (inclusive)；否则（遇到非空白字符）返回 None。
        """
        curr = pos
        # 计算实际扫描的上限
        limit = min(self.length, endpos + 1)
        
        while curr < limit:
            c = self.src[curr]
            if c in (' ', '\t'):
                curr += 1
            elif c == '\n':
                return curr  # match \n，return position
            elif c == '\r':
                # Handle \r\n
                if curr + 1 < limit and self.src[curr + 1] == '\n':
                    return curr + 1
                return curr
            else:
                return None  # Non-space char (like '\a'), not Hard Break
                
        return None

    def find(self, patt: re.Pattern) -> Optional[MatchedRange]:
        return find(self.src, patt, self.pos)

    def find_bangs(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_BANGS, self.pos)

    def find_whitespace(self, start: Optional[int] = None) -> Optional[MatchedRange]:
        if start is None:
            start = self.pos

        return find(self.src, self._PATT_WHITESPACE, start)

    def find_blockquote_prefix(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_BLOCKQUOTE_PREFIX, self.pos)

    def find_caption_start(self) -> Optional[MatchedRange]:
        """Matches ^ followed by any number of space or tab"""
        return find(self.src, self._PATT_CAPTION_START, self.pos)

    def find_footnotestart(self):
        return find(self.src, self._PATT_FOOTNOTE_START, self.pos)

    def find_reference_definition(self):
        return find(self.src, self._PATT_REFERENCE_DEFINITION, self.pos)

    def find_thematic_break(self):
        return find(self.src, self._PATT_THEMATIC_BREAK, self.pos)

    def find_list_marker(self):
        return find(self.src, self._PATT_LIST_MARKER, self.pos)

    def find_task_list_marker(self):
        return find(self.src, self._PATT_TASK_LIST_MARKER, self.pos)

    def find_table_row(self, start: Optional[int] = None):
        if start is None:
            start = self.pos
        return find(self.src, self._PATT_TABLE_ROW, start)

    def find_row_sep(self):
        # :-: |
        # :- |
        # -: |
        # - |
        return find(self.src, self._PATT_ROW_SEP, self.pos)

    def find_next_bar_or_tick(self):
        return find(self.src, self._PATT_NEXT_BAR_OR_TICK, self.pos)

    def find_word(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_WORD, self.pos)

    def find_div_fence_start(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_DIV_FENCE_START, self.pos)

    def find_div_fence_end(self, start: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_DIV_FENCE_END, start)

    def find_div_fence(self):
        return find(self.src, self._PATT_DIV_FENCE, self.pos)

    def find_code_fence(self):
        return find(self.src, self._PATT_CODE_FENCE, self.pos)

    def find_special(self, start: int, end: int) -> Optional[int]:
        """Find special characters"""
        m = self._RE_SPECIAL.search(self.src, start, end)

        if m:
            return m.start()

        return None

    def find_backtick_at_least_one(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_BACKTICKS1, pos, endpos)

    def find_opening_backtick(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        # Find zero or more backtick
        return find(self.src, self._PATT_BACKTICKS0, pos, endpos)

    def find_raw_attribute(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_RAW_ATTRIBUTE, pos, endpos)

    def find_double_dollar(self, pos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_DOUBLE_DOLLARS, pos)

    def find_single_dollar(self, pos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_BACKSLASH, pos)

    def find_backslash(self, pos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_BACKSLASH, pos)

    def find_punctuation(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_PUNCTUATION, pos, endpos)

    

    def find_autolink(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        # <([^<>\s]+)>
        # <https://pandoc.org/lua-filters>
        # <me@example.com>
        return find(self.src, self._PATT_AUTOLINK, pos, endpos)

    def find_delimiter(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_DELIM, pos, endpos)

    def find_symbol(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_SYMBOL, pos, endpos)

    def find_two_periods(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_TWO_PERIODS, pos, endpos)

    def find_note_reference(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        """
        Find pattern like `^foo]`
        """
        return find(self.src, self._PATT_NOTE_REFERENCE, pos, endpos)

    def scan_note_reference(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        if self.src[pos] != '^':
            return None

        start = pos
        pos = pos + 1
        while pos <= endpos:
            c = self.src[pos]
            if c == ']':
                return MatchedRange(
                    start=start,
                    end=pos,
                    captures=[self.src[start:pos+1]]
                )
            else:
                pos = pos + 1

        return None

    def has_brace(self, i: int) -> bool:

        if 1 <= i < self.length and self.src[i-1] == '{':
            return True

        if 0 <= i < self.length - 1 and self.src[i+1] == '}':
            return True

        return False

    def can_open_single_quote(self, pos: int) -> bool:
        """Checks if char at pos can be followed by single quote.

        - ` '`
        - `\t'`
        - `\r'`
        - `\n'`
        - `"'`
        - `''`
        - `-'`
        - `('`
        - `['`
        """
        if pos < 0: # do not allow negative number
            return False
        
        if pos == 0: # start
            return True

        return self.src[pos-1] in ' \t\r\n"\'-(['    

    def find_trailing_space_tab(self, span: Range) -> int:
        """Find out trailing space starting position
        
        Returns:
            int: the position of first non-space char from backward
        """
        start = span.start
        end = span.end

        while end >= start and self.src[end] in self._SPACE_TAB:
            end = end - 1

        return end

    def find_trailing_space(self, span: Range) -> int:
        start = span.start
        end = span.end
        while end >= start  and self.src[end] == ' ':
            end = end - 1

        return end

    def is_space(self, i: int) -> bool:
        return self.src[i] == ' '

    def is_whitespace(self, i: int) -> bool:
        if i < 0 or i >= self.length:
            return True
        return self.src[i] in self._WHITESPACE

    def is_crlf(self, i: int):
        """
        Check if the char at i is \r and the next is \n.
        """
        if i+1 >= self.maxoffset:
            return False
        return self.src[i] == '\r' and self.src[i+1] == '\n'

    def is_bang(self, i: int) -> bool:
        return self.src[i] == '!'

    def is_backslash(self, i: int) -> bool:
        return self.src[i] == '\\'

    def is_left_bracket(self, i: int) -> bool:
        return self.src[i] == '['

    def is_left_paren(self, i: int) -> bool:
        return self.src[i] == '('

    def is_left_brace(self, i: int) -> bool:
        return self.src[i] == '{'

    def is_right_brace(self, i: int) -> bool:
        return self.src[i] == '}'

    

    