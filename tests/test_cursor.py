import unittest

from typing import List

from djot.experimental.cursor import (
    Cursor,
    LineContext,
)
from djot.experimental.block.attribute import (
    AttributeRule,
)
from djot.experimental.block.context import (
    ParsingContext,
)
        

class TestCursor(unittest.TestCase):
    def test_start_newline(self):
        text = "hello\nworld\n  foo\n\nbar"
        #       012345 678901 234567 8 901

        actual: List[LineContext] = []

        cursor = Cursor(text)
        line = cursor.next_line(LineContext())
        while line is not None:
            actual.append(line)
            line = cursor.next_line(line)

        expected = [
            LineContext(0, 5, 0),
            LineContext(6, 11, 6),
            LineContext(12, 17, 12),
            LineContext(18, 18, 18),
            LineContext(19, 22, 19),
        ]

        self.assertEqual(expected, actual)

    def test_skip_space(self):
        text = '>  - item one'
        #       012345678901

        cursor = Cursor(text)

        next_ctx = cursor.skip_frame_space(
            LineContext(0, 10, 1)
        )

        self.assertEqual(
            next_ctx,
            LineContext(0, 10, 3),
        )

        next_ctx = cursor.skip_frame_space(
            LineContext(0, 10, 4)
        )

        self.assertEqual(
            next_ctx,
            LineContext(0, 10, 5),
        )

    def test_peek_line(self):
        text = '{.foo\n#bar\nkey=val key2="val1\nval2"}'
        #       012345 67890 12345678

        cursor = Cursor(text)
        line = cursor.next_line(LineContext())

        assert line is not None

        rule = AttributeRule()
        result = rule.try_open(ParsingContext(cursor, line))

        for e in result.events:
            print(e)


if __name__ == '__main__':
    unittest.main()
