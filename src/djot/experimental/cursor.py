from typing import NamedTuple


class LineContext(NamedTuple):
    line_num: int
    line_start: int # current line start position in global text.
    line_end: int
    indent: int = 0
    pos: int = 0

class Cursor:

    _SPACE_TAB = ' \t'

    def __init__(self, src: str) -> None:
        src = src.replace('\r\n', '\n')
        if src and src[-1] != '\n':
            src += '\n'

        self.src = src
        self.length = len(src)

        self._line_start = 0
        self._line_end = 0
        self._indent = 0
        self._pos = 0

    def find_line_end(self, line_start: int) -> int:
        i = self.src.find('\n', line_start)
        if i == -1:
            return self.length
        else:
            return i

    def skip_leading_space(self, line_start: int, line_end: int) -> int:
        new_pos = line_start

        while new_pos < line_end and self.src[new_pos] in self._SPACE_TAB:
            new_pos += 1

        return new_pos


    def start_newline(self, line_start: int = 0):
        """
        Reset Line Context
        """
        self._indent = 0
        self._line_start = line_start
        self._line_end = self.find_line_end(line_start)

