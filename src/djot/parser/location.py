from typing import List

from ..common import SourceLoc

def get_line_starts(text: str) -> List[int]:
    """获取字符串中所有换行符的位置（包括起始位置 -1）
    
    Args:
        text: 输入文本
        
    Returns:
        换行符位置列表，第一个元素为 -1
        
    Examples:
        >>> get_line_starts("hello\nworld\n")
        [-1, 5, 11]
    """
    starts = [-1]
    # Or an approach to avoid python loop:
    # pos = -1
    # while True:
    #     pos = text.find('\n', pos + 1)
    #     if pos == -1:
    #         break
    #     starts.append(pos)
    for i, char in enumerate(text):
        if char == '\n':
            starts.append(i)
    return starts

def get_source_loc(linestarts: List[int], pos: int) -> SourceLoc:
    numlines = len(linestarts)
    bottom = 0
    top = numlines - 1
    line = 0
    col = 0
    while not line:
        mid = bottom + (top - bottom) // 2
        if linestarts[mid] > pos: # lower part
            top = mid
        elif linestarts[mid] <= pos:
            # Reaching the last line, or pos is within mid line and mid+1 line.
            if mid == top or linestarts[mid + 1] > pos:
                line = mid + 1
                col = pos - linestarts[mid]
            else:
                if bottom == mid and bottom < top:
                    bottom = mid + 1
                else:
                    bottom = mid

    return SourceLoc(line, col, pos)