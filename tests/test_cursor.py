import unittest

from typing import List

from djot.common import Range
from djot.cursor import (
    Cursor,
    LineContext,
)
from djot.token import (
    DivFenceToken,
    CodeFenceToken,
    RefDefToken,
    FootnoteDefToken,
)
class TestCursor(unittest.TestCase):
    def test_new_line(self):
        text = "hello\nworld\n  foo\n\nbar"
        #       012345 678901 234567 8 901

        actual: List[LineContext] = []

        cursor = Cursor(text)

        while cursor.next_line():
            actual.append(cursor.current_line)

        expected = [
            LineContext(0, 5, 0),
            LineContext(6, 11, 6),
            LineContext(12, 17, 12),
            LineContext(18, 18, 18),
            LineContext(19, 22, 19),
        ]

        self.assertEqual(actual, expected)


    def test_advance_line(self):
        text = "hello\nworld\n  foo\n\nbar"
        #       012345 678901 234567 8 901

        cursor = Cursor(text)
        cursor.next_line()
        self.assertFalse(cursor.advance_line(LineContext()))

        self.assertTrue(cursor.advance_line(LineContext(
            start_offset=6,
            end_offset=11,
            pos=6,
        )))

    def test_advance_pos(self):
        text = "hello\nworld\n  foo\n\nbar"
        #       012345 678901 234567 8 901

        cursor = Cursor(text)
        cursor.next_line()

        cursor.advance_pos(3)

        self.assertEqual(cursor.current_line, LineContext(
            start_offset=0,
            end_offset=5,
            pos=3,
        ))

        self.assertEqual(cursor.current_line, LineContext(
            start_offset=0,
            end_offset=5,
            pos=3,
        ))

    def test_skip_frame_space(self):
        text = "hello\nworld\n  foo\n\nbar"
        #       012345 678901 234567 8 901

        cursor = Cursor(text)
        cursor.next_line()
        cursor.next_line()
        cursor.next_line()

        cursor.skip_frame_space()

        self.assertEqual(cursor.current_line, LineContext(
            start_offset=12,
            end_offset=17,
            pos=14,
        ))
        self.assertEqual(cursor.indent, 2)

    def test_peek_line(self):
        text = "hello\nworld\n  foo\n\nbar"
        #       012345 678901 234567 8 901

        cursor = Cursor(text)
        cursor.next_line()

        self.assertEqual(cursor.peek_line(cursor.current_line), LineContext(
            start_offset=6,
            end_offset=11,
            pos=6,
        ))

    def test_locate_line(self):
        text = "hello\nworld\n  foo\n\nbar"
        #       012345 678901 234567 8 901

        cursor = Cursor(text)
        cursor.next_line()

        actual = cursor.locate_line(8)
        expected = LineContext(
            start_offset=6,
            end_offset=11,
            pos=6,
        )

        self.assertEqual(actual, expected)

    def test_div_start(self):
        text = ":::: foo \nhello\n\nhi\n::::"
        #       0123456789 012345 6 789 0123

        cursor = Cursor(text)

        actual = cursor.find_div_start(0)

        expected = DivFenceToken(
            colon_span=Range(
                start=0,
                end=4,
            ),
            colons='::::',
            lang_span=Range(
                start=5,
                end=7
            )
        )

        self.assertEqual(actual, expected)

    def test_div_end(self):
        cases = [
            (
            #    0123
                ":::\n",
                ":::",
                Range(0, 2)
            ),
            (
            #    01234
                ":::: \n",
                "::::",
                Range(0, 3)
            ),
            (
            #    01234
                "::: \n",
                "::",
                None
            ),
        ]

        for text, borders, expected in cases:
            with self.subTest(text):
                cursor = Cursor(text)
                actual = cursor.find_div_end(0, borders)
                self.assertEqual(actual, expected)

    def test_code_start(self):
        cases = [
            (
            #    012345678901
                "```` python\n",
                CodeFenceToken(
                    border_span=Range(
                        start=0,
                        end=3,
                    ),
                    borders='````',
                    lang_span=Range(
                        start=5,
                        end=10
                    )
                )
            ),
            (
            #    01234
                "````\n",
                CodeFenceToken(
                    border_span=Range(
                        start=0,
                        end=3,
                    ),
                    borders='````',
                    lang_span=None
                )
            ),
            (
            #    012345678901
                "```` =html\n",
                CodeFenceToken(
                    border_span=Range(
                        start=0,
                        end=3,
                    ),
                    borders='````',
                    lang_span=Range(
                        start=5,
                        end=9
                    ),
                    is_raw=True
                )
            ),
        ]

        for text, expected in cases:
            with self.subTest(text):
                cursor = Cursor(text)
                actual = cursor.find_code_start(0)
                self.assertEqual(actual, expected)

    def test_code_end(self):
        cases = [
            (
            #    0123
                "```\n",
                "```",
                Range(0, 2)
            ),
            (
            #    01234
                "```` \n",
                "````",
                Range(0, 3)
            ),
            (
            #    01234
                "```` \n",
                "```",
                None
            ),
        ]

        for text, borders, expected in cases:
            cursor = Cursor(text)
            actual = cursor.find_code_end(0, borders)
            self.assertEqual(actual, expected)

    def test_ref_def(self):
        cases = [
            (
                #01234567890 12345
                "[foo]: bar\n baz\n",
                10,
                RefDefToken(
                    label_span=Range(
                        start=0,
                        end=4,
                    ),
                    label="foo",
                    value_span=Range(
                        start=7,
                        end=9
                    )
                ),
            ),
            (
                #0123456 7890
                "[foo]:\n bar",
                6,
                RefDefToken(
                    label_span=Range(
                        start=0,
                        end=4
                    ),
                    label="foo",
                    value_span=None,
                ),
            ),
        ]

        for text, endpos, expected in cases:
            with self.subTest(text):
                cursor = Cursor(text)
                actual = cursor.find_ref_def(0, endpos)
                self.assertEqual(actual, expected)

    def test_fn_def(self):
        text = "[^note]: This is a"
        #       0123456789

        cursor = Cursor(text)

        actual = cursor.find_footnote_def(0, 8)

        self.assertEqual(actual, FootnoteDefToken(
            label_span=Range(
                start=2,
                end=5
            ),
            label="note",
            end_pos=8,
        ))

    def test_symbol(self):
        text = ":symbol:"
        #       01234567

        cursor = Cursor(text)

        actual = cursor.find_symbol(0, len(text))

        self.assertEqual(actual, Range(
            start=0,
            end=7
        ))


        
        




if __name__ == '__main__':
    unittest.main()
