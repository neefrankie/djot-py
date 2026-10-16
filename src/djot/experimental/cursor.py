from typing import NamedTuple


class LineContext(NamedTuple):
    line_num: int
    start: int # current line start position in global text.
    end: int