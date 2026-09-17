import re
from typing import Optional

from .common import MatchedRange
from .find import find
from .common import Range


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
    # Math optional :, followed by at least one or more -,
    # followed by optional :, followed by optinal space/tab,
    # followed by pipe, followed by optional space.
    # :-: |
    # :- |
    # -: |
    # - |
    _PATT_ROW_SEP = re.compile(r'(:?)--*(:?)([ \t]*\|[ \t]*)')
    _PATT_NEXT_BAR_OR_TICK = re.compile(r'[^`|\r\n]*(?:[|]|`+)')
    _PATT_WORD = re.compile(r'\w+\s')
    _PATT_ENDLINE = re.compile(r'[ \t]*\r?\n')
    _PATT_DIV_FENCE_START = re.compile(r'(::::*)[ \t]*')
    _PATT_DIV_FENCE_END = re.compile(r'([\w_-]*)[ \t]*\r?\n')
    _PATT_DIV_FENCE = re.compile(r'(::::*)[ \t]*\r?\n')
    _PATT_CODE_FENCE = re.compile(r'(~~~~*|````*)([ \t]*)([^ \t\r\n`]*)[ \t]*\r?\n')


    # TODO: should we collect all the match logic in InputText?
    # If so, does it actually play the role of a Lexer?
    
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
        
        return ord(self.src[i]) == 10 or ord(self.src[i]) == 13 # \n or \r

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

        while self.is_space_or_tab_at(newpos):
            newpos += 1

        self.indent = newpos - self.line_start
        self.pos = newpos

    def is_space_or_tab_at(self, i: int) -> bool:
        if i >= self.length:
            return False
        return ord(self.src[i]) == 32 or ord(self.src[i]) == 9

    def new_span(self, start: int, end: int) -> Range:
        return Range(
            start=min(start, self.maxoffset),
            end=min(end, self.maxoffset)
        )

    def current_span(self) -> Range:
        return Range(
            start=min(self.pos, self.maxoffset),
            end=min(self.pos, self.maxoffset)
        )

    def current_line_span(self) -> Range:
        return Range(
            start=min(self.pos, self.maxoffset),
            end=min(self.eol_end, self.maxoffset)
        )

    def find(self, patt: re.Pattern) -> Optional[MatchedRange]:
        return find(self.src, patt, self.pos)

    def find_from(self, patt: re.Pattern, start: int) -> Optional[MatchedRange]:
        return find(self.src, patt, start)

    def find_bangs(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_BANGS, self.pos)

    def find_whitespace(self, start: Optional[int] = None) -> Optional[MatchedRange]:
        if not start:
            return find(self.src, self._PATT_WHITESPACE, self.pos)

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

    def find_table_row(self):
        return find(self.src, self._PATT_TABLE_ROW, self.pos)

    def find_row_sep(self):
        return find(self.src, self._PATT_ROW_SEP, self.pos)

    def ind_next_bar_or_tick(self):
        return find(self.src, self._PATT_NEXT_BAR_OR_TICK, self.pos)

    def find_word(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_WORD, self.pos)

    def find_endline(self, start: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_ENDLINE, start)

    def find_div_fence_start(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_DIV_FENCE_START, self.pos)

    def find_div_fence_end(self, start: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_DIV_FENCE_END, start)

    def find_div_fence(self):
        return find(self.src, self._PATT_DIV_FENCE, self.pos)

    def find_code_fence(self):
        return find(self.src, self._PATT_CODE_FENCE, self.pos)


    def next_char(self) -> Optional[str]:
        if self.pos > self.maxoffset:
            return None

        return self.src[self.pos]

    def is_crlf(self, i: int):
        """
        Check if the char at i is \r and the next is \n.
        """
        if i >= self.length:
            return False
        return ord(self.src[i]) == 13 and ord(self.src[i+1]) == 10