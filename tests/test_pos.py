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


if __name__ == "__main__":
    unittest.main()