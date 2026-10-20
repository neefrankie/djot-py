from dataclasses import dataclass, replace
import re

from djot.common import Range, MatchedRange

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
    start_offset: int = -1 # current line start position in global text.
    end_offset: int = -1
    pos: int = -1 # current char position in global text.

    def __repr__(self) -> str:
        return f'LineContext(start_offset={self.start_offset}, end_offset={self.end_offset}, pos={self.pos})'

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

    _SPACE_TAB = ' \t'
    _PATT_WORD = re.compile(r'\w+\s')
    _WHITESPACE = ' \t\r\n'
    # Inline
    _RE_SPECIAL = re.compile(
        r'''[\r\n"'()*+.:<=\[\\\]^_`${}~-]'''
    )
    # {=FORMAT}
    _PATT_RAW_ATTRIBUTE = re.compile(r'\{=[^\s{}`]+\}')

    def __init__(self, src: str) -> None:
        src = src.replace('\r\n', '\n')
        if src and src[-1] != '\n':
            src += '\n'

        self.src = src
        self.length = len(src)

        self.current_line: LineContext | None = None

    def new_span(self, start: int, end: int) -> Range:
        return Range(
            start=min(start, self.length-1),
            end=min(end, self.length-1)
        )

    def find_line_end(self, line_start: int) -> int:
        i = self.src.find('\n', line_start)
        if i == -1:
            return self.length
        else:
            return i

    def skip_frame_space(self, ctx: LineContext) -> LineContext:
        """
        Skip space from ctx.pos.
        
        Example:

        > - one
        >   
        >   - two

        It does not mean skipping leading spaces of a line.
        Instead, it means the column position of the first non-space character of a node at current level.
        """

        new_pos = ctx.pos
        
        while new_pos < ctx.end_offset and self.src[new_pos] in self._SPACE_TAB:
            new_pos += 1

        return replace(ctx, pos=new_pos)

    def next_line(self, last: LineContext) -> LineContext | None:
        """
        Reset Line Context
        """
        if last.end_offset >= self.length:
            return None
        
        start_offset = last.next_line_start
        end_offset = self.find_line_end(start_offset)

        ctx = LineContext(
            start_offset=start_offset,
            end_offset=end_offset,
            pos=start_offset
        )

        self.current_line = ctx

        return ctx

    def peek_line(self, previous: LineContext) -> LineContext | None:
        if previous.end_offset >= self.length:
            return None

        start_offset = previous.next_line_start
        end_offset = self.find_line_end(start_offset)

        return LineContext(
            start_offset=start_offset,
            end_offset=end_offset,
            pos=start_offset
        )

    def get_line_text(self, ctx: LineContext) -> str:
        return self.src[ctx.start_offset:ctx.end_offset+1]

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
        2. The rest of line is blank is start is in the middle of a line.
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
        return self.src[pos] in self._SPACE_TAB

    # Replace these regex:
    # re.compile(r'`*')
    # re.compile(r'`+')
    def count_char(self, ch: str, start: int) -> int:
        """Count consecutive chars"""

        if self.src[start] != ch:
            return 0
        
        i = start
        
        while i < self.length and self.src[i] == ch:
            i += 1
        
        return i - start

    def char_at(self, i: int) -> str | None:
        if i >= self.length:
            return None

        return self.src[i]


    def find_special(self, start: int, end: int) -> int | None:
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
    

    def find_raw_attribute(self, pos: int, endpos: int) -> MatchedRange | None:
        return find(self.src, self._PATT_RAW_ATTRIBUTE, pos, endpos)

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