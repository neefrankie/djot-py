from dataclasses import dataclass, field, replace
import re
import string
from typing import Final, List, Optional

from .common import Range
from .token import (
    DivFenceToken,
    CodeFenceToken,
    RefDefToken,
    FootnoteDefToken,
)

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

class Cursor:
    
    _PATT_NON_WHITESPACE = re.compile(r'[^ \t\r\n]+')
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

    # Inline
    _RE_SPECIAL = re.compile(
        r'''[\r\n"'()*+.:<=\[\\\]^_`${}~-]'''
    )
    # {=FORMAT}
    _FORMAT_EXCLUDES = ' \t\r\n\v\f{}`'
    
    # <https://pandoc.org/lua-filters>
    # <me@example.com>
    _PATT_AUTOLINK = re.compile(r'<([^<>\s]+)>')
    
    _SYMBOL_CHARS: Final = frozenset(string.ascii_letters + string.digits + "_+-")

    _DELIMITERS = '_*~^+=\'"-'
    
    # Replace `const pattNonspace = pattern("[^ \t\r\n]")` in djot.js.
    # When you want to determine if a single char is space,
    # use short plain str is always optimal in Python.
    _WHITESPACE = ' \t\r\n'
    _SPACE_TAB = ' \t'
    _DIV_LANG_CHARS: Final = frozenset(string.ascii_letters + string.digits + "-")
    
    def __init__(self, src: str) -> None:
        src = src.replace('\r\n', '\n')
        if src and src[-1] != '\n':
            src += '\n'

        self.src = src
        
        self.length = len(src)

        # Current line context
        self._pos = -1
        self._indent = 0
        self._line_start = -1
        self._line_end = -1

    def __repr__(self) -> str:
        return f'Cursor(line_start={self._line_start}, indent={self.indent}, line_end={self.line_end})'

    @property
    def current_line(self) -> LineContext:
        return LineContext(
            start_offset=self._line_start,
            end_offset=self.line_end,
            pos=self.pos
        )

    @property
    def line_end(self) -> int:
        return self._line_end

    @property
    def indent(self) -> int:
        return self._indent

    @property
    def is_eol_reached(self) -> bool:
        return self._pos == self.line_end

    @property
    def pos(self) -> int:
        return self._pos

    def new_span(self, start: int, end: int) -> Range:
        return Range(
            start=min(start, self.length-1),
            end=min(end, self.length-1)
        )

    # === Cursor movement ===

    def next_line(self) -> bool:
        """
        Move to next line
        """
        if self.length == 0:
            return False

        # last char should not have next line
        if self.line_end >= self.length - 1:
            return False

        next_start = self._line_end + 1
        next_end = self.find_next_newline(next_start)

        self._pos = next_start
        self._line_start = next_start
        self._line_end = next_end
        self._indent = 0

        return True

    def advance_line(self, target: LineContext) -> bool:
        if target.end_offset >= self.length:
            return False

        if target.start_offset <= self.current_line.end_offset:
            return False

        self._pos = target.pos
        self._line_start = target.start_offset
        self._line_end = target.end_offset
        self._indent = 0
        return True

    def advance_pos(self, newpos: int):
        if newpos >= self.length:
            raise Exception('Cursor.advance_pos: newpos is out of range')

        if newpos < self.pos:
            # Ensure monotony
            raise Exception('Cursor.advance_pos: newpos is less than current pos')

        if newpos == self.pos:
            return

        if self._line_start <= newpos <= self.line_end: # same line
            self._pos = newpos

        new_line = self.locate_line(newpos)
        assert new_line is not None

        self.advance_line(new_line)

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

        self._indent = newpos - self._line_start
        self._pos = newpos

    # === Locate line ===

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


    # === Whitespace ===

    def is_space_char(self, pos: int) -> bool:
        if pos >= self.length:
            return False
        
        return self.src[pos] == ' '

    def is_ahead_blank(self, start: int) -> bool:
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

    def is_trailing_blank(self, start: int, end: int) -> bool:
        # Replace re.compile(r'[ \t]*\r?\n') in djot.js
        if end >= self.length or self.src[end] != '\n':
            return False

        # not "" == True
        return not self.src[start:end].strip(' \t')

    def is_blank_span(self, start: int, end: int) -> bool:
        if self.src[end] == '\n':
            return all(c in self._SPACE_TAB for c in self.src[start:end])

        return all(c in self._SPACE_TAB for c in self.src[start:end+1])

    def is_whitespace(self, pos: int) -> bool:
        if pos < 0 or pos >= self.length:
            return True
        return self.src[pos] in self._WHITESPACE

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

    def find_non_whitespace(self, start: int) -> Optional[MatchedRange]:
        # [^ \t\r\n]+
        return find(self.src, self._PATT_NON_WHITESPACE, start)

    def has_space(self, start: int, line_end: int) -> bool:
        line_slice = self.src[start:line_end]
        if not line_slice:
            return True
        
        if ' ' in line_slice or '\t' in line_slice:
            return True

        return False

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

    def skip_space_tab(self, pos: int) -> int:
        while pos < self.length and self.src[pos] in self._SPACE_TAB:
            pos += 1

        return pos

    def get_adjusted_text_start(self, indent: Optional[int]) -> int:
        if indent is None:
            return self.pos
        if self.indent <= indent:
            return self.pos

        return self.pos - (self.indent - indent) # does this amount to indent itself?
    

    # === Repeated delimiters

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

    def find(self, patt: re.Pattern) -> Optional[MatchedRange]:
        return find(self.src, patt, self.pos)

    # === Char predicates ===

    def is_newline(self, pos: int) -> bool:
        if pos >= self.length:
            return False
        
        return self.src[pos] == '\n'

    def is_word(self, pos: int) -> bool:
        return find(self.src, self._PATT_WORD, pos) is not None

    # re.compile(r'[>][ \t\r\n]')
    def is_blockquote(self, pos: int) -> bool:
        if pos < 0 or pos + 1 >= self.length:
            return False

        return self.src[self.pos] == '>' and self.src[self.pos+1] in self._WHITESPACE

    def is_left_brace(self, pos: int) -> bool:
        return self.src[pos] == '{'

    def is_right_brace(self, pos: int) -> bool:
        return self.src[pos] == '}'

    def has_brace(self, i: int) -> bool:
        if 1 <= i < self.length and self.src[i-1] == '{':
            return True

        if 0 <= i < self.length - 1 and self.src[i+1] == '}':
            return True

        return False
    
    
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

    def find_caption_start(self, pos: int) -> int | None:
        """
        '^ ' starts a caption. However, the token is dropped.
        Caption starts after this token.
        """
        if self.src[pos] != '^':
            return None

        if pos + 1 >= self.length:
            return None

        if self.src[pos+1] not in self._SPACE_TAB:
            return None

        nsp = self.skip_space_tab(pos+1)

        return nsp

    def find_footnote_def(self, start: int, endpos: int) -> FootnoteDefToken | None:
        # \[\^([^\]]+)\]:[ \t\r\n]
        # '[^foo]: '
        if start < 0 or endpos >= self.length or start >= endpos:
            return None

        # After [, there should be at least a ^, and a label char.
        if start + 2 > endpos:
            return None
        
        if self.src[start] != '[':
            return None

        if self.src[start+1] != '^':
            return None

        label_start = start + 2 # after ^
        label_end = label_start # find right bracket.

        while self.src[label_end] != ']' and label_end < endpos:
            label_end += 1

        if self.src[label_end] != ']':
            return None

        # Extra position for ': '
        if label_end + 2 > endpos:
            return None

        if self.src[label_end+1] != ':':
            return None

        if self.src[label_end+2] not in self._WHITESPACE:
            return None

        return FootnoteDefToken(
            label_span=Range(label_start, label_end-1), # foo
            label=self.src[label_start:label_end], # foo
            end_pos=label_end+2 # space aftr :
        )

    def find_ref_def(self, start: int, endpos: int):
        # \[([^\]\r\n]*)\]:([ \t]+[^ \t\r\n]*|)[\r\n]
        # The pipe in [ \t]+[^ \t\r\n]*| means the first part is optional.
        # [google]: https://google.com
        if start < 0 or endpos >= self.length or start >= endpos:
            return None

        if self.src[start] != '[':
            return None

        label_end = start+1 # ]

        while self.src[label_end] not in ']\r\n' and label_end < endpos:
            label_end += 1

        if self.src[label_end] != ']':
            return None

        # If label_end points to ], there should be at least ':\n' left.
        if label_end+2 > endpos:
            return None

        if self.src[label_end+1] != ':':
            return None

        label_span = Range(start, label_end) # includs the []
        label = self.src[start+1:label_end]

        # URL could go to next line
        if self.src[label_end+2] == '\n':
            return RefDefToken(label_span, label, None)

        # Should have a space after colon.
        if self.src[label_end+2] not in self._SPACE_TAB:
            return None

        # Value should start after ': '.
        val_start = label_end + 3

        # Skip any leading space.
        val_start = self.skip_space_tab(val_start)
        val_end = val_start

        while self.src[val_end] not in self._WHITESPACE and val_end < self.length:
            val_end += 1

        if self.src[val_end] != '\n':
            return None

        val_span = Range(val_start, val_end-1) if val_end > val_start else None

        return RefDefToken(label_span, label, val_span)

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

    def find_div_start(self, pos: int) -> DivFenceToken | None:
        if pos < 0 or pos >= self.length:
            return None

        if self.src[pos] != ':':
            return None

        # Equivalent to original regex (::::*)[ \t]*
        n_colons = self.count_char(':', pos)
        if n_colons < 3:
            return None

        # After '::: '
        lang_start = self.skip_space_tab(pos + n_colons)
        lang_end = lang_start

        # re.compile(r'([\w_-]*)[ \t]*\r?\n', flags=re.ASCII)
        # [\w_-] is equivalent to [a-zA-Z0-9_] plus -.
        while self.src[lang_end] in self._DIV_LANG_CHARS:
            lang_end += 1

        if not self.is_ahead_blank(lang_end):
            return None

        colon_span = Range(
            start=pos,
            end=lang_start-1
        )

        return DivFenceToken(
            colon_span=colon_span,
            colons=self.src[pos:pos+n_colons],
            lang_span=Range(
                start=lang_start,
                end=lang_end - 1,
            ) if lang_end > lang_start else None,
        )

    def find_div_end(self, pos: int, borders: str) -> Range | None:
        # (::::*)[ \t]*\r?\n
        if pos < 0 or pos >= self.length:
            return None

        if not self.src.startswith(borders, pos):
            return None

        end_pos = pos + len(borders) - 1

        if not self.is_ahead_blank(end_pos + 1):
            return None

        return Range(
            start=pos,
            end=end_pos
        )

    def find_code_start(self, pos: int) -> CodeFenceToken | None:
        # (~~~~*|````*)([ \t]*)([^ \t\r\n`]*)[ \t]*\r?\n
        if self.src[pos] != '`' and self.src[pos] != '~':
            return None

        border_char = self.src[pos]

        border_len = self.count_char(border_char, pos)

        if border_len < 3:
            return None

        lang_start = self.skip_space_tab(pos + border_len)
        lang_end = lang_start

        while self.src[lang_end] not in self._WHITESPACE:
            lang_end += 1

        if not self.is_ahead_blank(lang_end):
            return None

        border_span = Range(
            start=pos,
            end=pos + border_len - 1,
        )
        is_raw = self.src[lang_start] == '='

        token = CodeFenceToken(
            border_span=border_span,
            borders=self.src[pos:pos+border_len],
            lang_span=Range(
                start=lang_start,
                end=lang_end - 1
            ) if lang_end > lang_start else None,
            is_raw=is_raw,
        )

        return token

    def find_code_end(self, pos: int, borders: str) -> Range | None:
        # (~~~~*|````*)[ \t]*\r?\n
        if pos < 0 or pos >= self.length:
            return None

        if not self.src.startswith(borders, pos):
            return None

        end_pos = pos + len(borders) - 1

        if not self.is_ahead_blank(end_pos + 1):
            return None

        return Range(
            start=pos,
            end=end_pos,
        )

    def find_raw_attribute(self, start: int, limit: int) -> Optional[Range]:
        # re.compile(r'\{=[^\s{}`]+\}', flags=re.ASCII)
        # {=FORMAT}
        if start < 0 or limit >= self.length or start >= limit:
            return None

        if self.src[start] != '{':
            return None

        if start + 3 > limit:
            return None

        if self.src[start+1] != '=':
            return None

        fmt_start = start + 2 # after '{='
        fmt_end = fmt_start
        while self.src[fmt_end] not in self._FORMAT_EXCLUDES:
            if fmt_end >= limit:
                return None
            fmt_end += 1

        if fmt_end == fmt_start:# not moved.
            return None
        
        if self.src[fmt_end] != '}':
            return None

        return Range(
            start=start,
            end=fmt_end,
        )

    def find_autolink(self, pos: int, endpos: int) -> Optional[MatchedRange]:
        # <([^<>\s]+)>
        # <https://pandoc.org/lua-filters>
        # <me@example.com>
        if pos < 0 or endpos >= self.length or pos > endpos:
            return None

        if self.src[pos] != '<':
            return None
        
        return find(self.src, self._PATT_AUTOLINK, pos, endpos)


    def find_symbol(self, start: int, limit: int) -> Range | None:
        # :smiley:
        # re.compile(r':[\w_+-]+:', flags=re.ASCII)
        if start < 0 or limit >= self.length or start > limit:
            return None
        
        if self.src[start] != ':':
            return None

        end = start + 1
        while self.src[end] in self._SYMBOL_CHARS and end < limit:
            end += 1

        if self.src[end] != ':':
            return None

        return Range(start, end)

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

    

    

    

    

    