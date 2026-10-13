from typing import List
import unittest

from djot.common import Range, Alignment
from djot.event import (
    Event,
    BlockContainer,
    InlineContainer,
    VerbatimKind,
    InlineLeaf,
    BlockLeaf,
    AttrKind,
)
from djot.input import InputText
from djot.block import EventParser
from djot.block.table import scan_table_pipe, parse_data_row
from djot.common import (
    ListStyle,
    OrderedStyle,
    ListKind,
    BulletKind,
    OrdinalKind,
    DelimiterKind,
)

def bullet_style(marker: str) -> ListStyle:
    return ListStyle(
        list_type=ListKind.BULLET,
        bullet=BulletKind(marker),
    )

def ordered_style(ordered_style: OrderedStyle) -> ListStyle:
    return ListStyle(
        list_type=ListKind.ORDERED,
        ordered=ordered_style,
    )

def definition_style() -> ListStyle:
    return ListStyle(
        list_type=ListKind.DEFINITION,
    )

def ordered_decimal_period():
    return ListStyle(
        list_type=ListKind.ORDERED,
        ordered=OrderedStyle(
            ordinal=OrdinalKind.DECIMAL,
            delimiter=DelimiterKind.PERIOD,
        ),
    )

def ordered_lower_roman_two_parens():
    return ListStyle(
        list_type=ListKind.ORDERED,
        ordered=OrderedStyle(
            ordinal=OrdinalKind.LOWER_ROMAN,
            delimiter=DelimiterKind.TWO_PARENS,
        )
    )

class TestEventParser(unittest.TestCase):
    def test_para(self):

        text = "hello *world*\n\nfoo"
        #       01234567890123 4 567

        expected = [
            Event.enter(Range(0, 0), BlockContainer.PARA),
            Event.str(0, 5),
            Event.enter(Range(6, 6), InlineContainer.STRONG),
            Event.str(7, 11),
            Event.exit(Range(12, 12), InlineContainer.STRONG),
            Event.exit(Range(13, 13), BlockContainer.PARA),
            Event.blankline(14, 14),
            Event.enter(Range(15, 15), BlockContainer.PARA),
            Event.str(15, 17),
            Event.exit(Range(18, 18), BlockContainer.PARA),
        ]

        parser = EventParser(text)
        events = list(parser.parse())
        self.assertEqual(events, expected)

    def test_blockquote(self):
        parser = EventParser("> hello\n> there\nlazy\n>\n> hi\n")
        #                     01234567 89012345 67890 12 34567
        expected = [
            Event.enter(Range(0, 0), BlockContainer.BLOCK_QUOTE),
            Event.enter(Range(2, 2), BlockContainer.PARA),
            Event.str(2, 6),
            Event.softbreak(7, 7),
            Event.str(10, 14),
            Event.softbreak(15, 15),
            Event.str(16, 19),
            Event.exit(Range(20, 20), BlockContainer.PARA),
            Event.blankline(22, 22),
            Event.enter(Range(25, 25), BlockContainer.PARA),
            Event.str(25, 26),
            Event.exit(Range(27, 27), BlockContainer.PARA),
            Event.exit(Range(27, 27), BlockContainer.BLOCK_QUOTE),
        ]

        actual = list(parser.parse())

        self.assertEqual(actual, expected)

    def test_heading(self):
        parser = EventParser("## hello\n## there\nlazy\n")
        actual = list(parser.parse())

        expected = [
            Event.enter(Range(0, 1), BlockContainer.HEADING),
            Event.str(3, 7),
            Event.softbreak(8, 8),
            Event.str(12, 16),
            Event.softbreak(17, 17),
            Event.str(18, 21),
            Event.exit(Range(22, 22), BlockContainer.HEADING)
        ]

        self.assertEqual(actual, expected)

    def test_reference_definitions(self):
        cases = [
            (
                'reference defition',
                "[foo]: bar\n baz\n",
                #01234567890 12345
                [
                    Event.enter(Range(0, 0), BlockContainer.REFERENCE_DEFINITION),
                    Event.leaf(Range(0, 4), InlineLeaf.REFERENCE_KEY),
                    Event.leaf(Range(7, 9), InlineLeaf.REFERENCE_VALUE),
                    Event.leaf(Range(12, 14), InlineLeaf.REFERENCE_VALUE),
                    Event.exit(Range(15, 15), BlockContainer.REFERENCE_DEFINITION)
                ]
            ),
            (
                'with url on next line',
                "[foo]:\n bar",
                #0123456 7890
                [
                    Event.enter(Range(0, 0), BlockContainer.REFERENCE_DEFINITION),
                    Event.leaf(Range(0, 4), InlineLeaf.REFERENCE_KEY),
                    Event.leaf(Range(8, 10), InlineLeaf.REFERENCE_VALUE),
                    Event.exit(Range(11, 11), BlockContainer.REFERENCE_DEFINITION)
                ]
            ),
            (
                'without space after colon para',
                "[foo]:bar",
                #012345678
                [
                    Event.enter(Range(0, 0), BlockContainer.PARA),
                    Event.str(0, 8),
                    Event.exit(Range(9, 9), BlockContainer.PARA),
                ]
            )
        ]

        for name, text, expected in cases:
            with self.subTest(name):
                parser = EventParser(text)
                self.assertEqual(list(parser.parse()), expected)

    def test_table(self):
        parser = EventParser(
            "| a | b |\n|--|--:|\n|33|2| "
           # 0123456789 012345678 9012345
        )

        expected = [
            Event.enter(Range(0, 0), BlockContainer.TABLE),
            Event.enter(Range(0, 0), BlockContainer.TABLE_ROW),
            Event.enter(Range(0, 0), InlineContainer.TABLE_CELL),
            Event.str(2, 2),
            Event.exit(Range(4, 4), InlineContainer.TABLE_CELL),
            Event.enter(Range(4, 4), InlineContainer.TABLE_CELL),
            Event.str(6, 6),
            Event.exit(Range(8, 8), InlineContainer.TABLE_CELL),
            Event.exit(Range(9, 9), BlockContainer.TABLE_ROW),
            Event.enter(Range(10, 10), BlockContainer.TABLE_ROW),
            Event.table_sep(11, 12).with_table_alignment(Alignment.DEFAULT),
            Event.table_sep(14, 16).with_table_alignment(Alignment.RIGHT),
            Event.exit(Range(17, 17), BlockContainer.TABLE_ROW),
            Event.enter(Range(19, 19), BlockContainer.TABLE_ROW),
            Event.enter(Range(19, 19), InlineContainer.TABLE_CELL),
            Event.str(20, 21),
            Event.exit(Range(22, 22), InlineContainer.TABLE_CELL),
            Event.enter(Range(22, 22), InlineContainer.TABLE_CELL),
            Event.str(23, 23),
            Event.exit(Range(24, 24), InlineContainer.TABLE_CELL),
            Event.exit(Range(25, 25), BlockContainer.TABLE_ROW),
            Event.exit(Range(26, 26), BlockContainer.TABLE)
        ]

        self.assertEqual(list(parser.parse()), expected)

    def test_code_block(self):
        parser = EventParser(
            "```` python\nif x == 3:\n  y = 4\n````\n"
        #    012345678901 23456789012 34567890 12345
        )

        actual = list(parser.parse())

        expected = [
            Event.enter(Range(0, 3), BlockContainer.CODE_BLOCK),
            Event.leaf(Range(5, 10), InlineLeaf.CODE_LANGUAGE),
            Event.str(12, 22),
            Event.str(23, 30),
            Event.exit(Range(31, 34), BlockContainer.CODE_BLOCK)
        ]

        self.assertEqual(actual, expected)

    def test_list_items(self):
        text = "- one\n- two\n1. three\n(iv) four\n\n - sub\n\n   two\n"
        #       012345 678901 234567890 1234567890 1 2345678 9 0123456

        actual = list(EventParser(text).parse())

        expected = [
            Event.enter(Range(0, 0), BlockContainer.LIST).with_list_styles([bullet_style('-')]),
            Event.enter(Range(0, 0), BlockContainer.LIST_ITEM).with_list_styles([bullet_style('-')]),
            Event.enter(Range(2, 2), BlockContainer.PARA),
            Event.str(2, 4),
            Event.exit(Range(5, 5), BlockContainer.PARA),
            Event.exit(Range(5, 5), BlockContainer.LIST_ITEM),
            Event.enter(Range(6, 6), BlockContainer.LIST_ITEM).with_list_styles([
                bullet_style('-')
            ]),
            Event.enter(Range(8, 8), BlockContainer.PARA),
            Event.str(8, 10),
            Event.exit(Range(11, 11), BlockContainer.PARA),
            Event.exit(Range(11, 11), BlockContainer.LIST_ITEM),
            # Event.exit(Range(12, 12), BlockContainer.LIST),
            Event.exit(Range(11, 11), BlockContainer.LIST), # NOTE: this is a fix of djot.js list closing position.
            Event.enter(Range(12, 13), BlockContainer.LIST).with_list_styles([
                ordered_decimal_period()
            ]),
            Event.enter(Range(12, 13), BlockContainer.LIST_ITEM).with_list_styles([
                ordered_decimal_period()
            ]),
            Event.enter(Range(15, 15), BlockContainer.PARA),
            Event.str(15, 19),
            Event.exit(Range(20, 20), BlockContainer.PARA),
            Event.exit(Range(20, 20), BlockContainer.LIST_ITEM),
            Event.exit(Range(20, 20), BlockContainer.LIST),
            Event.enter(Range(21, 24), BlockContainer.LIST).with_list_styles([
                ordered_lower_roman_two_parens()
            ]),
            Event.enter(Range(21, 24), BlockContainer.LIST_ITEM).with_list_styles([
                ordered_lower_roman_two_parens()
            ]),
            Event.enter(Range(26, 26), BlockContainer.PARA),
            Event.str(26, 29),
            Event.exit(Range(30, 30), BlockContainer.PARA),
            Event.blankline(31, 31),
            Event.enter(Range(33, 33), BlockContainer.LIST).with_list_styles([
                bullet_style('-')
            ]),
            Event.enter(Range(33, 33), BlockContainer.LIST_ITEM).with_list_styles([
                bullet_style('-')
            ]),
            Event.enter(Range(35, 35), BlockContainer.PARA),
            Event.str(35, 37),
            Event.exit(Range(38, 38), BlockContainer.PARA),
            Event.blankline(39, 39),
            Event.enter(Range(43, 43), BlockContainer.PARA),
            Event.str(43, 45),
            Event.exit(Range(46, 46), BlockContainer.PARA),
            Event.exit(Range(46, 46), BlockContainer.LIST_ITEM),
            Event.exit(Range(46, 46), BlockContainer.LIST),
            Event.exit(Range(46, 46), BlockContainer.LIST_ITEM),
            Event.exit(Range(46, 46), BlockContainer.LIST),
        ]

        self.assertEqual(actual, expected)

    def test_definition_list(self):
        text = ": orange\n\n  A citrus fruit.\n"
        #       012345678 9 012345678901234567
        actual = list(EventParser(text).parse())

        expected = [
            Event.enter(Range(0,0), BlockContainer.LIST).with_list_styles([
                definition_style(),
            ]),
            Event.enter(Range(0,0), BlockContainer.LIST_ITEM).with_list_styles([
                definition_style(),
            ]),
            Event.enter(Range(2,2), BlockContainer.PARA),
            Event.str(2,7),
            Event.exit(Range(8,8), BlockContainer.PARA),
            Event.blankline(9,9),
            Event.enter(Range(12,12), BlockContainer.PARA),
            Event.str(12,26),
            Event.exit(Range(27,27), BlockContainer.PARA),
            Event.exit(Range(27,27), BlockContainer.LIST_ITEM),
            Event.exit(Range(27,27), BlockContainer.LIST)

        ]

        self.assertEqual(actual, expected)

    def test_loose_list(self):
        cases = [
            (
                "- one\n\n  - two\n\n  - three\n",
                #012345 6 78901234 5 6789012345
                [
                    Event.enter(Range(0, 0), BlockContainer.LIST).with_list_styles([
                        bullet_style('-')
                    ]),
                    Event.enter(Range(0, 0), BlockContainer.LIST_ITEM).with_list_styles([
                        bullet_style('-')
                    ]),
                    Event.enter(Range(2, 2), kind=BlockContainer.PARA),
                    Event.str(2,4),
                    Event.exit(Range(5, 5), kind=BlockContainer.PARA),
                    Event.blankline(6,6),
                    Event.enter(Range(9, 9), kind=BlockContainer.LIST).with_list_styles([
                        bullet_style('-')
                    ]),
                    Event.enter(Range(9, 9), kind=BlockContainer.LIST_ITEM).with_list_styles([
                        bullet_style('-')
                    ]),
                    Event.enter(Range(11, 11), kind=BlockContainer.PARA),
                    Event.str(11, 13),
                    Event.exit(Range(14, 14), kind=BlockContainer.PARA),
                    Event.blankline(15, 15),
                    Event.exit(Range(15,15), kind=BlockContainer.LIST_ITEM),
                    Event.enter(Range(18, 18), kind=BlockContainer.LIST_ITEM).with_list_styles([
                        bullet_style('-')
                    ]),
                    Event.enter(Range(20, 20), kind=BlockContainer.PARA),
                    Event.str(20, 24),
                    Event.exit(Range(25, 25), kind=BlockContainer.PARA),
                    Event.exit(Range(25,25), kind=BlockContainer.LIST_ITEM),
                    Event.exit(Range(25,25), kind=BlockContainer.LIST),
                    Event.exit(Range(25,25), kind=BlockContainer.LIST_ITEM),
                    Event.exit(Range(25,25), kind=BlockContainer.LIST)
                ],
            ),
            (
                "- one\n  - two\n",
                #012345 67890123
                [
                    Event.enter(Range(0, 0), BlockContainer.LIST).with_list_styles([
                        bullet_style('-')
                    ]),
                    Event.enter(Range(0, 0), BlockContainer.LIST_ITEM).with_list_styles([
                        bullet_style('-')
                    ]),
                    Event.enter(Range(2,2), kind=BlockContainer.PARA),
                    Event.str(2,4),
                    Event.softbreak(5,5),
                    Event.str(8,12),
                    Event.exit(Range(13,13), kind=BlockContainer.PARA),
                    Event.exit(Range(13,13), kind=BlockContainer.LIST_ITEM),
                    Event.exit(Range(13,13), kind=BlockContainer.LIST),
                ],
            )
        ]

        for text, expected in cases:
            with self.subTest(text):
                print('\n')
                actual = list(EventParser(text).parse())
                for e in actual:
                    print(e)

    def test_captions(self):
        text = " ^ This is a\n*capt*\n\n"
        #       0123456789012 3456789 0
        parser = EventParser(text)
        actual = list(parser.parse())

        expected = [
            Event.enter(Range(3, 3), BlockContainer.CAPTION),
            Event.str(3, 11),
            Event.softbreak(12, 12),
            Event.enter(Range(13, 13), InlineContainer.STRONG),
            Event.str(14, 17),
            Event.exit(Range(18, 18), InlineContainer.STRONG),
            Event.exit(Range(19, 19), BlockContainer.CAPTION),
            Event.blankline(20, 20)
        ]

        self.assertEqual(actual, expected)

    def test_thematic_breaks(self):
        text = " - - - -\n"
        #       012345678

        parser = EventParser(text)
        actual = list(parser.parse())

        expected = [ 
            Event.leaf(Range(1, 8), BlockLeaf.THEMATIC_BREAK)
        ]

        self.assertEqual(actual, expected)

    def test_fenced_div(self):
        text = ":::: foo \nhello\n\nhi\n::::"
        #       0123456789 012345 6 789 0123
        parser = EventParser(text)
        actual = list(parser.parse())

        expected = [
            Event.enter(Range(0, 4), BlockContainer.DIV),
            Event.attr(Range(5, 7), AttrKind.CLASS),
            Event.enter(Range(10, 10), BlockContainer.PARA),
            Event.str(10, 14),
            Event.exit(Range(15, 15), BlockContainer.PARA),
            Event.blankline(16, 16),
            Event.enter(Range(17, 17), BlockContainer.PARA),
            Event.str(17, 18),
            Event.exit(Range(19, 19), BlockContainer.PARA),
            Event.exit(Range(20, 23), BlockContainer.DIV),
            Event.blankline(24, 24),
        ]

        self.assertEqual(actual, expected)

    def test_footnotes(self):
        text = "[^note]: This is a\nnote\n\n  second par\n\nafter note\n"
        #       0123456789012345678 90123 4 5678901234567 8 90123456789
        parser = EventParser(text)
        actual = list(parser.parse())

        expected = [
            Event.enter(Range(0, 0), BlockContainer.FOOTNOTE),
            Event.leaf(Range(2, 5), InlineLeaf.NOTE_LABEL),
            Event.enter(Range(9, 9), BlockContainer.PARA),
            Event.str(9, 17),
            Event.softbreak(18, 18),
            Event.str(19, 22),
            Event.exit(Range(23, 23), BlockContainer.PARA),
            Event.blankline(24, 24),
            Event.enter(Range(27, 27), BlockContainer.PARA),
            Event.str(27, 36),
            Event.exit(Range(37, 37), BlockContainer.PARA),
            Event.blankline(38, 38),
            # Event.exit(Range(39, 39), BlockContainer.FOOTNOTE),
            Event.exit(Range(38, 38), BlockContainer.FOOTNOTE), # NOTE: this is a fix of djot.js footenote closing position.
            Event.enter(Range(39, 39), BlockContainer.PARA),
            Event.str(39, 48),
            Event.exit(Range(49, 49), BlockContainer.PARA),
        ]

        self.assertEqual(actual, expected)

    def test_block_attributes(self):
        text = "{.foo}\n{#bar\n .baz}\nHello"
        #       0123456 789012 3456789 01234
        parser = EventParser(text)
        actual = list(parser.parse())

        expected = [
            Event.enter(Range(0, 0), BlockContainer.ATTRIBUTES),
            Event.attr(Range(1, 1), AttrKind.CLASS_MARKER),
            Event.attr(Range(2, 4), AttrKind.CLASS),
            Event.exit(Range(7, 7), BlockContainer.ATTRIBUTES),
            Event.enter(Range(7, 7), BlockContainer.ATTRIBUTES),
            Event.attr(Range(8, 8), AttrKind.ID_MARKER),
            Event.attr(Range(9, 11), AttrKind.ID),
            Event.attr(Range(14, 14), AttrKind.CLASS_MARKER),
            Event.attr(Range(15, 17), AttrKind.CLASS),
            Event.exit(Range(20, 20), BlockContainer.ATTRIBUTES),
            Event.enter(Range(20, 20), BlockContainer.PARA),
            Event.str(20, 24),
            Event.exit(Range(25, 25), BlockContainer.PARA)
        ]

        # self.assertEqual(actual, expected)
        # This test cannot pass as it is not supported.

    def test_block_attr_as_para(self):
        text = "{.foo\nbar *baz*\n\n"
        parser = EventParser(text)
        actual = list(parser.parse())

        expected = [
            Event.enter(Range(0, 0), BlockContainer.PARA),
            Event.str(0, 4),
            Event.softbreak(5, 5),
            Event.str(6, 9),
            Event.enter(Range(10, 10), InlineContainer.STRONG),
            Event.str(11, 13),
            Event.exit(Range(14, 14), InlineContainer.STRONG),
            Event.exit(Range(15, 15), BlockContainer.PARA),
            Event.blankline(16, 16)
        ]
        self.assertEqual(actual, expected)

        
class TestParsingTable(unittest.TestCase):
    def test_scan_table_pipe(self):
        cases = [
            (
                '| a | b |',
                (1, 8),
                [4, 8]
            ),
            (
                '| `|` | \\| |',
                #012345678 901
                (1, 12),
                [6, 11]
            )
        ]

        for text, args, expected in cases:
            with self.subTest(text):
                cursor = InputText(text)
                pos: List[int] = []
                start = args[0]
                end = args[1]
                while start <= end:
                    nextbar = scan_table_pipe(cursor, start, end)
                    if nextbar:
                        pos.append(nextbar)
                        start = nextbar + 1
                    else:
                        break

                self.assertEqual(pos, expected)

    def test_parse_data_row(self):
        text = '| `|` | \\| |'
               #01234567 8901

        actual = parse_data_row(InputText(text), Range(0, 11))

        expected = [
            Event.enter(Range(0, 0), BlockContainer.TABLE_ROW),
            Event.enter(Range(0, 0), InlineContainer.TABLE_CELL),
            Event.enter(Range(2, 2), VerbatimKind.VERBATIM),
            Event.str(3, 3),
            Event.exit(Range(4, 4), VerbatimKind.VERBATIM),
            Event.str(5, 5),
            Event.exit(Range(6, 6), InlineContainer.TABLE_CELL),
            Event.enter(Range(6, 6), InlineContainer.TABLE_CELL),
            Event.escape(8, 8),
            Event.str(9, 10),
            Event.exit(Range(11, 11), InlineContainer.TABLE_CELL),
            Event.exit(Range(11, 11), BlockContainer.TABLE_ROW),
        ]

        # if actual is not None:
        #     for e in actual:
        #         print(e)

        self.assertEqual(actual, expected)

if __name__ == '__main__':
    unittest.main()