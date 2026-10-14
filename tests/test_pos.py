import bisect
import unittest
from djot.common.pos import (
    SourceMap,
    get_line_starts,
    SourceLoc,
)

class TestPos(unittest.TestCase):

    def test_newlines(self):
        text = "hello\nworld\n"
        #       012345 678901
        actual = get_line_starts(text)
        expected = [-1, 5, 11]

        self.assertEqual(actual, expected)

    def test_source_loc(self):
        text = "hello\nworld\n"
        #       012345 678901
        source_map = SourceMap(text)

        actual = source_map.get_source_loc(3)
        expected = SourceLoc(line=1, col=4, offset=3)

        self.assertEqual(actual, expected)

    def test_bisect(self):
        newlines = [-1, 9, 10, 30]

        cases = [
            (5, 1),
            (9, 1),
            (10, 2),
            (20, 3),
            (30, 3),
            (31, 4),
            (-1, 0)
        ]

        for pos, expected in cases:
            idx = bisect.bisect_left(newlines, pos)
            self.assertEqual(idx, expected)

        


if __name__ == "__main__":
    unittest.main()