import unittest

from djot.common.list_style import (
    TaskList,
    BulletStyle,
    CheckboxStyle,
    OrdinalKind,
    classify_ordinal,
    OrderedListStyle,
    OrderedList,
    ListStyle,
    ListKind,
)
from djot.cursor import Cursor
from djot.token import ListMarkerToken
from djot.common import Range

class TestListStyles(unittest.TestCase):

    def test_parse_bullet(self):
        cases = [(
                '- ',
                ListMarkerToken(
                    start=0,
                    end=1,
                    marker='-',
                    styles=[
                        ListStyle(
                            list_type=ListKind.UNORDERED,
                            unordered=BulletStyle.DASH
                        )
                    ],
                    item_span=Range(0, 0),
                )
            ),
            (
                ': ',
                ListMarkerToken(
                    start=0,
                    end=1,
                    marker=':',
                    styles=[
                        ListStyle(
                            list_type=ListKind.DEFINITION,
                        )
                    ],
                    item_span=Range(0, 0),
                )
            ),
            (
                '- [ ] ',
                #012345
                ListMarkerToken(
                    start=0,
                    end=5,
                    marker='- [ ]',
                    styles=[
                        ListStyle(
                            list_type=ListKind.TASK,
                            task=TaskList(
                                style=BulletStyle.DASH,
                                checkbox=CheckboxStyle.EMPTY,
                            )
                        )
                    ],
                    item_span=Range(0, 4),
                    checkbox_span=Range(2, 4)
                )
            ),
            (
                '- [X] ',
                #012345
                ListMarkerToken(
                    start=0,
                    end=5,
                    marker='- [X]',
                    styles=[
                        ListStyle(
                            list_type=ListKind.TASK,
                            task=TaskList(
                                style=BulletStyle.DASH,
                                checkbox=CheckboxStyle.UPPER_X,
                            )
                        )
                    ],
                    item_span=Range(0, 4),
                    checkbox_span=Range(2, 4)
                )
            ),
            (
                '- [x] ',
                #012345
                ListMarkerToken(
                    start=0,
                    end=5,
                    marker='- [x]',
                    styles=[
                        ListStyle(
                            list_type=ListKind.TASK,
                            task=TaskList(
                                style=BulletStyle.DASH,
                                checkbox=CheckboxStyle.LOWER_X,
                            )
                        )
                    ],
                    item_span=Range(0, 4),
                    checkbox_span=Range(2, 4)
                )
            )
        ]

        for text, expected in cases:
            with self.subTest(text):
                cursor = Cursor(text)
                token = cursor.parse_list(0, len(text))
                self.assertEqual(token, expected)

    def test_classify_ordinal(self):
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
                    OrdinalKind.ROMAN_LOWER,
                    OrdinalKind.ALPHA_LOWER,
                ]
            ),
            (
                'a',
                [
                    OrdinalKind.ALPHA_LOWER,
                ]
            ),
            (
                'A',
                [
                    OrdinalKind.ALPHA_UPPER,
                ]
            ),
            (
                'iv',
                [
                    OrdinalKind.ROMAN_LOWER,
                ]
            ),
            (
                'XI',
                [
                    OrdinalKind.ROMAN_UPPER,
                ]
            )
        ]

        for text, expected in cases:
            with self.subTest(text):
                self.assertEqual(classify_ordinal(text), expected)

    def test_parse_ordered(self):
        cases = [
            (
                '1. ',
                #012
                ListMarkerToken(
                    start=0,
                    end=2,
                    marker='1.',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.DECIMAL,
                                style=OrderedListStyle.PERIOD
                            )
                        )
                    ],
                    item_span=Range(0, 1),
                )
            ),
            (
                '1) ',
                #012
                ListMarkerToken(
                    start=0,
                    end=2,
                    marker='1)',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.DECIMAL,
                                style=OrderedListStyle.PAREN
                            )
                        )
                    ],
                    item_span=Range(0, 1),
                )
            ),
            (
                '(1) ',
                #0123
                ListMarkerToken(
                    start=0,
                    end=3,
                    marker='(1)',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.DECIMAL,
                                style=OrderedListStyle.TWO_PARENS,
                            )
                        )
                    ],
                    item_span=Range(0, 2),
                )
            ),
            (
                'a. ',
                #012
                ListMarkerToken(
                    start=0,
                    end=2,
                    marker='a.',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ALPHA_LOWER,
                                style=OrderedListStyle.PERIOD
                            )
                        )
                    ],
                    item_span=Range(0, 1),
                )
            ),
            (
                'a) ',
                #012
                ListMarkerToken(
                    start=0,
                    end=2,
                    marker='a)',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ALPHA_LOWER,
                                style=OrderedListStyle.PAREN
                            )
                        )
                    ],
                    item_span=Range(0, 1),
                )
            ),
            (
                '(a) ',
                #0123
                ListMarkerToken(
                    start=0,
                    end=3,
                    marker='(a)',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ALPHA_LOWER,
                                style=OrderedListStyle.TWO_PARENS,
                            )
                        )
                    ],
                    item_span=Range(0, 2),
                )
            ),
            (
                'i. ',
                #012
                ListMarkerToken(
                    start=0,
                    end=2,
                    marker='i.',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ROMAN_LOWER,
                                style=OrderedListStyle.PERIOD
                            )
                        ),
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ALPHA_LOWER,
                                style=OrderedListStyle.PERIOD
                            )
                        )
                    ],
                    item_span=Range(0, 1),
                )
            ),
            (
                'i) ',
                #012
                ListMarkerToken(
                    start=0,
                    end=2,
                    marker='i)',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ROMAN_LOWER,
                                style=OrderedListStyle.PAREN
                            )
                        ),
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ALPHA_LOWER,
                                style=OrderedListStyle.PAREN
                            )
                        )
                    ],
                    item_span=Range(0, 1),
                )
            ),
            (
                '(i) ',
                #0123
                ListMarkerToken(
                    start=0,
                    end=3,
                    marker='(i)',
                    styles=[
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ROMAN_LOWER,
                                style=OrderedListStyle.TWO_PARENS,
                            )
                        ),
                        ListStyle(
                            list_type=ListKind.ORDERED,
                            ordered=OrderedList(
                                ordinal=OrdinalKind.ALPHA_LOWER,
                                style=OrderedListStyle.TWO_PARENS
                            )
                        )
                    ],
                    item_span=Range(0, 2),
                )
            )
        ]

        for text, expected in cases:
            with self.subTest(text):
                # self.assertEqual(parse_ordered_marker(text), expected)
                cursor = Cursor(text)
                token = cursor.parse_list(0, len(text))
                self.assertEqual(token, expected)


if __name__ == '__main__':
    unittest.main()