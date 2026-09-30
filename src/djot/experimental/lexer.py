from dataclasses import dataclass
from enum import Enum, auto
import re

class LineKind(Enum):
    HEADING = auto()
    TEXT = auto()
    BLANK = auto()
    BLOCK_QUOTE = auto()
    CODE_FENCE = auto()
    DIV_FENCE = auto()
    

@dataclass
class Span:
    start: int # inclusive
    end: int # exclusive

@dataclass
class Line:
    kind: LineKind
    span: Span
    indent: int
    
class LineLexer:

    def __init__(self, src: str):
        self.src = src
        self.length = len(src)
        self.cursor = 0

    def next_line(self) -> Line | None:
        if self.cursor >= self.length:
            return None

        start = self.cursor
        end = self._find_line_end(start)
        self.cursor = end # to next line start

        span = Span(start, end)
        non_space_pos = self._skip_spaces(start, end)
        indent = non_space_pos - start

        if non_space_pos >= end or self.src[non_space_pos] in '\r\n':
            return Line(LineKind.BLANK, span, indent)

        if self._is_heading(non_space_pos, end):
            return Line(LineKind.HEADING, span, indent)

        if self._is_blockquote(non_space_pos, end):
            return Line(LineKind.BLOCK_QUOTE, span, indent)

        return Line(LineKind.TEXT, span, indent)

    def _find_line_end(self, start: int) -> int:
        """Find next line end.
        
        Return starting position of next line, \r\n or \n is included.
        """
        i = start
        while i < self.length:
            ch = self.src[i]
            if ch == '\n':
                return i + 1
            if ch == '\r':
                if i + 1 < self.length and self.src[i + 1] == '\n':
                    return i + 2
                return i + 1
            i += 1

        return self.length

    def _skip_spaces(self, start: int, end: int) -> int:
        """Count leading spaces."""
        i = start
        while i < end and self.src[i] in ' \t':
            i += 1
        return i

    def _is_heading(self, pos: int, end: int) -> bool:
        """Detect heading from first non-space char."""
        count = 0
        i = pos

        while i < end and self.src[i] == '#':
            count += 1
            i += 1

        if count == 0 or count > 6:
            return False

        # Must immediately followed by space, tab or endline.
        if i >= end or self.src[i] in ' \t\r\n':
            return True

        return False

    def _is_blockquote(self, pos: int, end: int) -> bool:
        """Check blockquote from firstt non-space char."""
        if pos < end and self.src[pos] == '>':
            if pos + 1 >= end or self.src[pos + 1] in ' \t\r\n':
                return True

        return False


        
