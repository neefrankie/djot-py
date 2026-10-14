import bisect
from dataclasses import dataclass
from typing import List


@dataclass
class SourceLoc:
    line: int # starting from 1
    col: int # starting from 1
    offset: int # 0-based

    def __str__(self) -> str:
        return f'{self.line}:{self.col}:{self.offset}'

@dataclass
class Pos:
    start: SourceLoc
    end: SourceLoc

    def __str__(self) -> str:
        return f'{self.start} - {self.end}'

def get_line_starts(text: str) -> List[int]:
    """Find all newline position in a string.
    The first position is -1 so that subsequent col is 1-based.
    
    Args:
        text: input text
        
    Returns:
        List of nelinwe positions. First one is -1
        
    Examples:
        >>> get_line_starts("hello\nworld\n")
        [-1, 5, 11]
    """
    starts = [-1]
    
    pos = -1
    while True:
        pos = text.find('\n', pos + 1)
        if pos == -1:
            break
        starts.append(pos)

    return starts

class SourceMap:
    def __init__(self, text: str):
        # linestarts saves the position of all newlines, 
        # with -1 indicating the fist line's starting poiint
        self.line_starts: list[int] = get_line_starts(text)

    def get_source_loc(self, pos: int) -> SourceLoc:
        # bisect_right find the first newline position that is greater than pos.
        # Subtract 1 to get the the last index of the newline position
        # aht is less or equal to pos
        line_idx = bisect.bisect_right(self.line_starts, pos) - 1
        
        line = line_idx + 1
        col = pos - self.line_starts[line_idx]
        return SourceLoc(line=line, col=col, offset=pos)

    def calc_pos(self, start: int, end: int):
        start_loc = self.get_source_loc(start)
        end_loc = self.get_source_loc(end)
        return Pos(
            start=start_loc,
            end=end_loc,
        )

def get_source_loc_manual(self, pos: int) -> SourceLoc:
        """
        Find the position of last newline that is less or equal to pos.

        If i is the last index that meets linestarts[i] <= pos,
        then line number is i + 1 (starting from 1).
        Col is pos - linestarts[i].
        """
        low, high = 0, len(self.line_starts) - 1
        ans = 0

        # 寻找 <= pos 的最大索引 ans
        while low <= high:
            mid = (low + high) // 2
            if self.line_starts[mid] <= pos:
                ans = mid
                low = mid + 1   # 尝试往右找更大的满足条件的索引
            else:
                high = mid - 1  # 太大了，往左缩

        line = ans + 1
        col = pos - self.line_starts[ans]
        return SourceLoc(line=line, col=col, offset=pos)