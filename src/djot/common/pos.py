import bisect
from dataclasses import dataclass
from typing import List


@dataclass
class SourceLoc:
    line: int # starting from 1
    col: int # starting from 1
    offset: int # 0-based

    def __str__(self) -> str:
        return f'line={self.line}, col={self.col}, offset={self.offset}'

@dataclass
class Pos:
    start: SourceLoc
    end: SourceLoc

    def __str__(self) -> str:
        return f'start({self.start}), end({self.end})'

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
    """
    SourceMap is used to calculate source code position in a human readable axis approach.

    Mathmatical deduction to determine line and column position.

    We use the following text as an example:

    ```
    # testing\n\n> testing _testing_\n
    0123456789 0 12345678901234567890
    ```

    Write in in human readable format:

    ```
    # testing

    > testing _testing_
    ```

    It will generate a list of newline start `line_starts`: `[-1, 9, 10, 30]`.
    The indices of this list are line numbers. The first element `-1` plays a special role
    to ensure `line` and `col` start from 1.
    
    What is the line of the first newline at position 9?
    It shuld be line 1 according to human habits.
    A character at `p` of line 1 should satisfy `-1 < p <= 9`.
    So does the second line `9 < p <=10`,
    and the third line `10 < p <= 30`.

    The condition could be expressed as:

    - Of all the newline positions less than p, find the last one. P is one the next line. Or
    - Of all the newline positions greater than p, find the first one. P is one the previous line.

    In Python standard library, there is `bisect.bisect_left` and `bisect.bisect_right`.
    Which one fits the requirements?

    bisect.bisect_left:
    The returned insertion point ip partitions the array a into two slices such that all(elem < x for elem in a[lo : ip]) is true for the left slice and all(elem >= x for elem in a[ip : hi]) is true for the right slice.
    """
    def __init__(self, text: str):
        # linestarts saves the position of all newlines, 
        # with -1 indicating the fist line's starting poiint
        self.line_starts: List[int] = get_line_starts(text)

    def get_source_loc(self, pos: int) -> SourceLoc:
        """
        bisect_left find the position i where all items before i
        are less than pos and all items from i are greater or equal to pos.
        This i is exactly the target line.
        """
        line_idx = bisect.bisect_left(self.line_starts, pos)

        # Pos should always be in the range [0, len(text)),
        # so bisect_left should never return a value before index 1
        # or after the last index.
        if line_idx == 0 or line_idx == len(self.line_starts):
            raise Exception(f'Source map invalid position: {pos}')

        previous_line_start = self.line_starts[line_idx-1]
        col = pos - previous_line_start
        return SourceLoc(line=line_idx, col=col, offset=pos)

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