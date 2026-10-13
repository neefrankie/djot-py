import unittest

from djot.common.list_style import (
    parse_task_marker,
    TaskStyle,
    BulletKind,
    CheckboxKind,
    OrdinalKind,
    parse_ordinal_style,
    DelimiterKind,
    ParsedMarker,
    parse_ordered_delimiter,
    OrderedStyle,
    parse_ordered_marker,
    ListStyle,
    parse_list_styles,
    ListKind,
)

class TestListStyles(unittest.TestCase):

    def test_parse_task(self):
        cases = [
            (
                '- [ ]',
                TaskStyle(
                    bullet=BulletKind.DASH,
                    checkbox=CheckboxKind.EMPTY,
                )
            ),
            (
                '- [X]',
                TaskStyle(
                    bullet=BulletKind.DASH,
                    checkbox=CheckboxKind.UPPER_X,
                )
            ),
            (
                '- [x]',
                TaskStyle(
                    bullet=BulletKind.DASH,
                    checkbox=CheckboxKind.LOWER_X,
                )
            )
        ]

        for text, expected in cases:
            with self.subTest(text):
                self.assertEqual(parse_task_marker(text), expected)

    def test_parse_ordinal(self):
        cases = [
            (
                '1',
                [
                    OrdinalKind.DECIMAL
                ]
            ),
            (
                'i',
                [
                    OrdinalKind.LOWER_ROMAN,
                    OrdinalKind.LOWER_ALPHA,
                ]
            ),
            (
                'a',
                [
                    OrdinalKind.LOWER_ALPHA,
                ]
            ),
            (
                'A',
                [
                    OrdinalKind.UPPER_ALPHA,
                ]
            ),
            (
                'iv',
                [
                    OrdinalKind.LOWER_ROMAN,
                ]
            ),
            (
                'XI',
                [
                    OrdinalKind.UPPER_ROMAN,
                ]
            )
        ]

        for text, expected in cases:
            with self.subTest(text):
                self.assertEqual(parse_ordinal_style(text), expected)

    def test_parse_delimiter(self):
        cases = [
            (
                '1',
                None
            ),
            (
                '1.',
                ParsedMarker(
                    delimiter=DelimiterKind.PERIOD,
                    ordinal='1'
                )
            ),
            (
                '1)',
                ParsedMarker(
                    delimiter=DelimiterKind.PAREN,
                    ordinal='1'
                )
            ),
            (
                '(1)',
                ParsedMarker(
                    delimiter=DelimiterKind.TWO_PARENS,
                    ordinal='1'
                )
            ),
        ]

        for text, expected in cases:
            with self.subTest(text):
                self.assertEqual(parse_ordered_delimiter(text), expected)

    def test_parse_ordered(self):
        cases = [
            (
                '1.',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.DECIMAL,
                        delimiter=DelimiterKind.PERIOD
                    )
                ]
            ),
            (
                '1)',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.DECIMAL,
                        delimiter=DelimiterKind.PAREN
                    )
                ]
            ),
            (
                '(1)',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.DECIMAL,
                        delimiter=DelimiterKind.TWO_PARENS,
                    )
                ]
            ),
            (
                'a.',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ALPHA,
                        delimiter=DelimiterKind.PERIOD
                    )
                ]
            ),
            (
                'a)',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ALPHA,
                        delimiter=DelimiterKind.PAREN
                    )
                ]
            ),
            (
                '(a)',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ALPHA,
                        delimiter=DelimiterKind.TWO_PARENS,
                    )
                ]
            ),
            (
                'i.',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ROMAN,
                        delimiter=DelimiterKind.PERIOD
                    ),
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ALPHA,
                        delimiter=DelimiterKind.PERIOD
                    )
                ]
            ),
            (
                'i)',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ROMAN,
                        delimiter=DelimiterKind.PAREN
                    ),
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ALPHA,
                        delimiter=DelimiterKind.PAREN
                    )
                ]
            ),
            (
                '(i)',
                [
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ROMAN,
                        delimiter=DelimiterKind.TWO_PARENS,
                    ),
                    OrderedStyle(
                        ordinal=OrdinalKind.LOWER_ALPHA,
                        delimiter=DelimiterKind.TWO_PARENS
                    )
                ]
            )
        ]

        for text, expected in cases:
            with self.subTest(text):
                self.assertEqual(parse_ordered_marker(text), expected)

    def test_parse_list(self):
        cases = [
            (
                '-',
                [
                    ListStyle(
                        list_type=ListKind.BULLET,
                        bullet=BulletKind.DASH
                    )
                ]

            ),
            (
                ':',
                [
                    ListStyle(
                        list_type=ListKind.DEFINITION,
                    )
                ]

            ),
            (
                '- [ ]',
                [
                    ListStyle(
                        list_type=ListKind.TASK,
                        task=TaskStyle(
                            bullet=BulletKind.DASH,
                            checkbox=CheckboxKind.EMPTY
                        )
                    )
                ]

            ),
            (
                'i.',
                [
                    ListStyle(
                        list_type=ListKind.ORDERED,
                        ordered=OrderedStyle(
                            ordinal=OrdinalKind.LOWER_ROMAN,
                            delimiter=DelimiterKind.PERIOD
                        )
                    ),
                    ListStyle(
                        list_type=ListKind.ORDERED,
                        ordered=OrderedStyle(
                            ordinal=OrdinalKind.LOWER_ALPHA,
                            delimiter=DelimiterKind.PERIOD
                        )
                    )
                ]
            ),
        ]

        for text, expected in cases:
            with self.subTest(text):
                self.assertEqual(parse_list_styles(text), expected)


if __name__ == '__main__':
    unittest.main()