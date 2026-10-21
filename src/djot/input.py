from dataclasses import dataclass, field, replace
import re
import string
from typing import List, Optional

from .common import Range

@dataclass(slots=True, frozen=True)
class MatchedRange:
    start: int
    end: int
    captures: List[str] = field(default_factory=list)

    
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

@dataclass(slots=True, frozen=True)
class LineContext:
    start_offset: int = 0 # current line start position in global text.
    end_offset: int = 0
    pos: int = 0 # current char position in global text.

    @property
    def is_reaching_end(self) -> bool:
        if self.end_offset == -1:
            return False
        
        return self.pos == self.end_offset

    @property
    def current_column(self) -> int:
        return self.pos - self.start_offset

    @property
    def next_line_start(self) -> int:
        return self.end_offset + 1

    def new_pos(self, pos: int) -> 'LineContext':
        return replace(self, pos=pos)

    def to_line_end(self) -> 'LineContext':
        return replace(self, pos=self.end_offset)

    def adjust_indented_start(self, indent: int | None) -> 'LineContext':
        if indent is None:
            return self
        if self.pos <= indent + self.start_offset:
            return self

        return replace(self, pos=indent)

class InputText:
    
    _PATT_NON_WHITESPACE = re.compile(r'[^ \t\r\n]+')
    _PATT_CAPTION_START = re.compile(r'\^[ \t]+')
    _PATT_FOOTNOTE_START = re.compile(r'\[\^([^\]]+)\]:[ \t\r\n]')
    _PATT_REFERENCE_DEFINITION = re.compile(r'\[([^\]\r\n]*)\]:([ \t]+[^ \t\r\n]*|)[\r\n]')
    _PATT_THEMATIC_BREAK = re.compile(r'[-*][ \t]*[-*][ \t]*[-*][-* \t]*\r?\n')
    _PATT_LIST_MARKER = re.compile(
        r'(:?[-*+:]' # - or * or + or :, this group includes possible task list.
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
    _PATT_DIV_FENCE_END = re.compile(r'([\w_-]*)[ \t]*\r?\n', flags=re.ASCII)
    _PATT_DIV_FENCE = re.compile(r'(::::*)[ \t]*\r?\n')
    _PATT_CODE_FENCE = re.compile(r'(~~~~*|````*)([ \t]*)([^ \t\r\n`]*)[ \t]*\r?\n')

    # Inline
    _RE_SPECIAL = re.compile(
        r'''[\r\n"'()*+.:<=\[\\\]^_`${}~-]'''
    )
    # {=FORMAT}
    _PATT_RAW_ATTRIBUTE = re.compile(r'\{=[^\s{}`]+\}')
    
    # <https://pandoc.org/lua-filters>
    # <me@example.com>
    _PATT_AUTOLINK = re.compile(r'<([^<>\s]+)>')
    
    _PATT_SYMBOL = re.compile(r':[\w_+-]+:', flags=re.ASCII)
    _SYMBOL_CHARS = string.ascii_letters + string.digits + "_+-"

    _DELIMITERS = '_*~^+=\'"-'
    
    # Replace `const pattNonspace = pattern("[^ \t\r\n]")` in djot.js.
    # When you want to determine if a single char is space,
    # use short plain str is always optimal in Python.
    _WHITESPACE = ' \t\r\n'
    _SPACE_TAB = ' \t'
    _CR_LF = '\r\n'
    
    def __init__(self, src: str) -> None:
        src = src.replace('\r\n', '\n')
        if src and src[-1] != '\n':
            src += '\n'

        self.src = src
        
        self.length = len(src)

        # Current line context
        self._pos = -1
        self.indent = 0
        self.line_start = -1
        self.line_end = -1

    def __repr__(self) -> str:
        return f'Cursor(line_start={self.line_start}, indent={self.indent}, line_end={self.line_end})'

    @property
    def current_line(self) -> LineContext:
        return LineContext(
            start_offset=self.line_start,
            end_offset=self.line_end,
            pos=self.pos
        )

    @property
    def is_eol_reached(self) -> bool:
        return self.pos == self.line_end

    @property
    def pos(self) -> int:
        return self.pos

    def next_line(self) -> bool:
        """
        Move to next line
        """
        if self.length == 0:
            return False
        
        if self.line_end >= self.length - 1:
            return False

        self._pos = self.line_end + 1
        self.line_start = self.pos + 1
        self.line_end = self.find_next_newline(self.line_start)
        self.indent = 0

        return True
    def advance_line(self, target: LineContext) -> bool:
        if target.end_offset >= self.length:
            return False

        if target.start_offset <= self.current_line.end_offset:
            return False

        self._pos = target.pos
        self.line_start = target.start_offset
        self.line_end = target.end_offset
        self.indent = 0
        return True

    def advance_pos(self, newpos: int):
        if newpos >= self.length:
            raise Exception('Cursor.advance_pos: newpos is out of range')

        if newpos < self.pos:
            # Ensure monotony
            raise Exception('Cursor.advance_pos: newpos is less than current pos')

        if newpos == self.pos:
            return

        if self.line_start <= newpos <= self.line_end: # same line
            self._pos = newpos

        new_line = self.locate_line(newpos)
        assert new_line is not None

        self.advance_line(new_line)

    def peek_line(self, previous: LineContext) -> LineContext | None:
        if previous.end_offset >= self.length:
            return None

        start_offset = previous.next_line_start
        end_offset = self.find_next_newline(start_offset)

        return LineContext(
            start_offset=start_offset,
            end_offset=end_offset,
            pos=start_offset
        )

    def locate_line(self, pos: int) -> LineContext | None:
        if pos >= self.length or pos < 0:
            return None

        end_offset = self.find_next_newline(pos)
        prev_newline = self.find_previous_newline(pos)
        start_offset = prev_newline + 1

        if start_offset > end_offset:
            return None

        return LineContext(
            start_offset=start_offset,
            end_offset=end_offset,
            pos=start_offset
        )

    

    def find_next_newline(self, pos: int) -> int:
        i = self.src.find('\n', pos)
        if i == -1:
            return self.length
        else:
            return i

    def find_previous_newline(self, pos: int) -> int:
        return self.src.rfind('\n', 0, pos) # -1 is valid.

    def new_span(self, start: int, end: int) -> Range:
        return Range(
            start=min(start, self.maxoffset),
            end=min(end, self.maxoffset)
        )

    def skip_frame_space(self):
        """
        This is not what is usually considered as skipping leading spaces.
        It is actually skipping leading space of current node.
        For example:

        ```
        > - item 1
        0123456789
        ```

        When a bockquote rule opened, skip space to
        position 2.
        When a list item rule opened, skip space to
        position 5.
        So the indent is not actaully whitespace indentation.
        It might be more properly described as the 
        column position of first non-space character of a node.
        """
        newpos = self.pos

        while newpos < self.length and self.src[newpos] in self._SPACE_TAB:
            newpos += 1

        self.indent = newpos - self.line_start
        self._pos = newpos

    def is_left_brace(self, pos: int) -> bool:
            return self.src[pos] == '{'
    
    def is_right_brace(self, pos: int) -> bool:
        return self.src[pos] == '}'

    def is_newline(self, pos: int) -> bool:
        return self.src[pos] == '\n'

    def is_space(self, pos: int) -> bool:
        return self.src[pos] == ' '

    def peek_is_blank(self, start: int) -> bool:
        """
        Find out if a line is blank from start to next newline.
        It deals with two cases:
        1. A plain blank line if start points to the start of a line.
        2. The rest of line is blank if start is in the middle of a line.
        """
        while start < self.length:
            c = self.src[start]
            if c in self._SPACE_TAB:
                start += 1
            elif c == '\n':
                return True
            else:
                return False # non-space

        return False # EOF without newline.

    def is_blank_span(self, start: int, end: int) -> bool:
        if self.src[end] == '\n':
            return all(c in self._SPACE_TAB for c in self.src[start:end])

        return all(c in self._SPACE_TAB for c in self.src[start:end+1])

    def is_word(self, pos: int) -> bool:
        return find(self.src, self._PATT_WORD, pos) is not None

    def is_whitespace(self, pos: int) -> bool:
        if pos < 0 or pos >= self.length:
            return True
        return self.src[pos] in self._WHITESPACE


    # Replace these regex:
    # re.compile(r'`*')
    # re.compile(r'`+')
    def count_char(self, ch: str, start: Optional[int] = None) -> int:
        """Count consecutive chars"""
        if start is None:
            pos = self.pos
        else:
            pos = start
        
        if self.src[pos] != ch:
            return 0
        
        i = pos
        
        while i < self.length and self.src[i] == ch:
            i += 1
        
        return i - pos

    def char_at(self, pos: int) -> Optional[str]:
        if pos >= self.length:
            return None

        return self.src[pos]


    def find_special(self, start: int, end: int) -> Optional[int]:
        """Find special characters
        
        This functions tries to follow the behavior in of 
        findSpecial in djot.js, which includes endpos based on
        if (result && result.index <= endpos).
        Python Pattern.search, however, does not include endpos.
        Here's the doc:
        The optional parameter endpos limits how far the string will be searched; it will be as if the string is endpos characters long, so only the characters from pos to endpos - 1 will be searched for a match. 
        """
        m = self._RE_SPECIAL.search(self.src, start, end+1)

        if m:
            return m.start()

        return None

    def right_find_space_tab(self, span: Range) -> int:
        """Find out trailing space starting position
        
        Returns:
            int: the position of first non-space char from backward
        """
        start = span.start
        end = span.end

        while end >= start and self.src[end] in self._SPACE_TAB:
            end = end - 1

        return end

    def right_find_space_char(self, span: Range) -> int:
        start = span.start
        end = span.end
        while end >= start and self.src[end] == ' ':
            end = end - 1

        return end

    # re.compile(r'[>][ \t\r\n]')
    def is_blockquote(self, pos: int) -> bool:
        if pos < 0 or pos + 1 >= self.length:
            return False

        return self.src[self.pos] == '>' and self.src[self.pos+1] in self._WHITESPACE

    @property
    def maxoffset(self) -> int:
        return self.length - 1

    @property
    def is_eof(self) -> bool:
        return self.pos >= self.length

    

    @property
    def is_current_before_eol(self) -> bool:
        return self.pos < self.line_end

    def start_newline(self):
        """
        Reset Line Context
        """
        self.next_line()

    

    def skip_space_from(self, start: int) -> int:
        newpos = start
        while newpos < self.length and self.src[newpos] in self._SPACE_TAB:
            newpos += 1

        return newpos

    def is_eol_at(self, i: int) -> bool:
        """
        Check if char at i is newline or return char.
        """
        if i >= self.length:
            return False

        return self.src[i] == '\n'

    

    def is_rest_of_line_blank(self, start: int) -> bool:
        while start < self.length:
            c = self.src[start]
            if c in self._SPACE_TAB:
                start += 1
            elif c == '\n':
                return True
            else:
                return False # non-space

        return False # EOF without newline.
        
    # re.compile(r'[ \t]*\r?\n')
    def find_blank_end(self, pos: int, endpos: int) -> Optional[int]:
        """
        Scan from pos to the end of line, if there's only space in between,
        return the EOL index; otherwise returns None.
        """
        curr = pos
        # 计算实际扫描的上限
        limit = min(self.length, endpos + 1)
        
        while curr < limit:
            c = self.src[curr]
            if c in self._SPACE_TAB:
                curr += 1
            elif c == '\n':
                return curr  # match \n，return position
            else:
                return None  # Non-space char (like '\a'), not Hard Break
                
        return None

    
    def advance_to_new_line(self):
        self._pos = (self.line_end or self.pos) + 1
    
    

    def get_adjusted_text_start(self, indent: Optional[int]) -> int:
        if indent is None:
            return self.pos
        if self.indent <= indent:
            return self.pos

        return self.pos - (self.indent - indent) # does this amount to indent itself?

    
    
    

    def peek_char_is(self, ch: str) -> bool:
        if self.pos >= self.length or self.pos < 0:
            return False
        
        return self.src[self.pos] == ch

    


    

    # re.compile(r'''['!"#%&\\'()*+,\-./:;<=>?@\[\]^`{|}~']''')
    def is_ascii_punct(self, pos: int) -> bool:
        if pos >= self.length:
            return False

        return self.src[pos] in string.punctuation

    # re.compile(r'\$\$')
    def has_double_dollars(self, pos: int) -> bool:
        if pos < 0 or pos+1 >= self.length:
            return False
        
        return self.src[pos] == '$' and self.src[pos+1] == '$'

    # re.compile(r'\$')
    def has_single_dollar(self, pos: int) -> bool:
        if pos < 0 or pos >= self.length:
            return False
        return self.src[pos] == '$' and self.src[pos+1] != '$'

    # re.compile(r'\.\.')
    def has_two_period(self, pos: int, endpos: int) -> bool:
        limit = min(self.length-1, endpos)
        if pos < 0 or pos >= limit:
            return False

        return self.src[pos] == '.' and self.src[pos+1] == '.'


    # re.compile(r'\\')
    def is_backslash(self, pos: int) -> bool:
        if pos < 0 or pos >= self.length:
            return False
        
        return self.src[pos] == '\\'

    # re.compile(r'''[_*~^+='"-]''')
    def is_delimiter(self, pos: int) -> bool:
        if pos < 0 or pos >= self.length:
            return False

        return self.src[pos] in self._DELIMITERS
    
    

    def peek_is_whitespace(self) -> bool:
        if self.pos < 0 or self.pos >= self.length:
            return False

        return self.src[self.pos] in self._WHITESPACE

    

    def is_not_whitespace(self, pos: int) -> bool:
        """
        Minics the regex "[^ \t\r\n]".
        JS versions uses new RegExp(patt, 'yd') to build a regex,
        and then use patt.lastIndex to set search start position.
        lastIndex is a non-negative integer, 
        and should be less than the length of the string,
        otherwise no match will be found.
        Therefore for out of range pos, we return false.
        """
        if pos < 0 or pos >= self.length:
            return False

        return self.src[pos] not in self._WHITESPACE

    def find_non_whitespace(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_NON_WHITESPACE, self.pos)

    # re.compile(r'[>][ \t\r\n]')
    def peek_is_blockquote_prefix(self) -> bool:
        if self.pos < 0 or self.pos + 1 >= self.length:
            return False

        return self.src[self.pos] == '>' and self.src[self.pos+1] in self._WHITESPACE

    def is_crlf(self, i: int):
        """
        Check if the char at i is \r and the next is \n.
        """
        if i+1 >= self.length:
            return False
        return self.src[i] == '\r' and self.src[i+1] == '\n'

    def is_cr_or_lf(self, i: int) -> bool:
        if i >= self.length:
            return False

        return self.src[i] in self._CR_LF

    def is_bang(self, i: int) -> bool:
        return self.src[i] == '!'

    def is_left_bracket(self, i: int) -> bool:
        return self.src[i] == '['

    def is_left_paren(self, i: int) -> bool:
        return self.src[i] == '('

    

    def is_hat(self, i: int) -> bool:
        return self.src[i] == '^'

    def is_dash(self, i: int) -> bool:
        return self.src[i] == '-'

    def is_pipe(self, i: int) -> bool:
        return self.src[i] == '|'

    def find(self, patt: re.Pattern) -> Optional[MatchedRange]:
        return find(self.src, patt, self.pos)

    

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

    def find_table_sep_cell(self, start: int):
        # :-: |
        # :- |
        # -: |
        # - |
        return find(self.src, self._PATT_ROW_SEP, start)

    def find_next_bar_or_tick(self):
        return find(self.src, self._PATT_NEXT_BAR_OR_TICK, self.pos)

    def find_div_fence_start(self) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_DIV_FENCE_START, self.pos)

    def find_div_fence_end(self, start: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_DIV_FENCE_END, start)

    def find_div_fence(self):
        return find(self.src, self._PATT_DIV_FENCE, self.pos)

    def find_code_fence(self):
        return find(self.src, self._PATT_CODE_FENCE, self.pos)

    def find_raw_attribute(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        return find(self.src, self._PATT_RAW_ATTRIBUTE, pos, endpos)

    def find_autolink(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        # <([^<>\s]+)>
        # <https://pandoc.org/lua-filters>
        # <me@example.com>
        return find(self.src, self._PATT_AUTOLINK, pos, endpos)


    def find_symbol(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        if self.src[pos] != ':':
            return None

        if pos + 1 > endpos or self.src[pos+1] not in self._SYMBOL_CHARS:
            return None
        
        return find(self.src, self._PATT_SYMBOL, pos, endpos)

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
        if pos <= 0:
            return True

        return self.src[pos-1] in ' \t\r\n"\'-(['    

    

    

    

    

    