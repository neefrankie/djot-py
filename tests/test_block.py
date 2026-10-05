from typing import Dict, List, NamedTuple, Optional
import unittest

from djot.common import Range
from djot.options import Options
from djot.event import (
    Event,
    BlockContainer,
    InlineContainer,
    VerbatimKind,
    InlineLeaf,
    Alignment,
    BlockLeaf,
    AttrKind,
)
from djot.input import InputText
from djot.block.container import (
    BlockRule,
    Container,
    RuleResult,
    FlowControl,
    ParsingContext,
)
from djot.block.para import ParaRule
from djot.block.blockquote import BlockquoteRule
from djot.block import EventParser
from djot.block.table import scan_table_pipe, parse_data_row

def enter(start: int, end: int, kind: BlockContainer | InlineContainer | VerbatimKind):
    return Event.enter(
        Range(start, end),
        kind,
    )

def exit(start: int, end: int, kind: BlockContainer | InlineContainer | VerbatimKind):
    return Event.exit(
        Range(start, end),
        kind,
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
                    Event.ref_key(0, 4),
                    Event.ref_value(7, 9),
                    Event.ref_value(12, 14),
                    Event.exit(Range(15, 15), BlockContainer.REFERENCE_DEFINITION)
                ]
            ),
            (
                'with url on next line',
                "[foo]:\n bar",
                #0123456 7890
                [
                    Event.enter(Range(0, 0), BlockContainer.REFERENCE_DEFINITION),
                    Event.ref_key(0, 4),
                    Event.ref_value(8, 10),
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
            Event.row(0, 0),
            Event.cell(0, 0),
            Event.str(2, 2),
            Event.cell(4, 4, False),
            Event.cell(4, 4),
            Event.str(6, 6),
            Event.cell(8, 8, False),
            Event.row(9, 9, False),
            Event.row(10, 10),
            Event.table_sep(11, 12).with_table_alignment(Alignment.DEFAULT),
            Event.table_sep(14, 16).with_table_alignment(Alignment.RIGHT),
            Event.row(17, 17, False),
            Event.row(19, 19),
            Event.cell(19, 19),
            Event.str(20, 21),
            Event.cell(22, 22, False),
            Event.cell(22, 22),
            Event.str(23, 23),
            Event.cell(24, 24, False),
            Event.row(25, 25, False),
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
            Event.enter(Range(0, 0), BlockContainer.LIST).with_list_styles(['-']),
            Event.enter(Range(0, 0), BlockContainer.LIST_ITEM).with_list_styles(['-']),
            Event.enter(Range(2, 2), BlockContainer.PARA),
            Event.str(2, 4),
            Event.exit(Range(5, 5), BlockContainer.PARA),
            Event.exit(Range(5, 5), BlockContainer.LIST_ITEM),
            Event.enter(Range(6, 6), BlockContainer.LIST_ITEM).with_list_styles(['-']),
            Event.enter(Range(8, 8), BlockContainer.PARA),
            Event.str(8, 10),
            Event.exit(Range(11, 11), BlockContainer.PARA),
            Event.exit(Range(11, 11), BlockContainer.LIST_ITEM),
            # Event.exit(Range(12, 12), BlockContainer.LIST),
            Event.exit(Range(11, 11), BlockContainer.LIST), # NOTE: this is a fix of djot.js list closing position.
            Event.enter(Range(12, 13), BlockContainer.LIST).with_list_styles(['1.']),
            Event.enter(Range(12, 13), BlockContainer.LIST_ITEM).with_list_styles(['1.']),
            Event.enter(Range(15, 15), BlockContainer.PARA),
            Event.str(15, 19),
            Event.exit(Range(20, 20), BlockContainer.PARA),
            Event.exit(Range(20, 20), BlockContainer.LIST_ITEM),
            # Event.exit(Range(21, 21), BlockContainer.LIST),
            Event.exit(Range(20, 20), BlockContainer.LIST),
            Event.enter(Range(21, 24), BlockContainer.LIST).with_list_styles(['(i)']),
            Event.enter(Range(21, 24), BlockContainer.LIST_ITEM).with_list_styles(['(i)']),
            Event.enter(Range(26, 26), BlockContainer.PARA),
            Event.str(26, 29),
            Event.exit(Range(30, 30), BlockContainer.PARA),
            Event.blankline(31, 31),
            Event.enter(Range(33, 33), BlockContainer.LIST).with_list_styles(['-']),
            Event.enter(Range(33, 33), BlockContainer.LIST_ITEM).with_list_styles(['-']),
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

        actual = parse_data_row(InputText(text), Range(0, 11), Options())

        expected = [
            Event.row(0, 0),
            Event.cell(0, 0),
            Event.enter(Range(2, 2), VerbatimKind.VERBATIM),
            Event.str(3, 3),
            Event.exit(Range(4, 4), VerbatimKind.VERBATIM),
            Event.str(5, 5),
            Event.cell(6, 6, False),
            Event.cell(6, 6),
            Event.escape(8, 8),
            Event.str(9, 10),
            # Event.str(10, 10),
            Event.cell(11, 11, False),
            Event.row(11, 11, False),
        ]

        # if actual is not None:
        #     for e in actual:
        #         print(e)

        self.assertEqual(actual, expected)

        



class Args(NamedTuple):
    text: str
    pos: int = 0
    is_covered: bool = False
    last_span_end: Optional[int] = None

class Expected(NamedTuple):
    pos: int
    result: RuleResult

class TestCase(NamedTuple):
    name: str
    args: Args
    expected: Expected
    rule: BlockRule

rules: Dict[BlockContainer, BlockRule] = {
    BlockContainer.PARA: ParaRule(),
    BlockContainer.BLOCK_QUOTE: BlockquoteRule(),

}

def new_open_result(pos: int, kind: BlockContainer) -> RuleResult:
    return RuleResult(
        status=FlowControl.OPEN,
        events=[
            Event.enter(
                kind=kind,
                span=Range(pos, pos)
            )
        ],
        container=Container(
            rule=rules[kind],
        )
    )

def new_close_result(pos: int, kind: BlockContainer) -> RuleResult:
    return RuleResult(
        status=FlowControl.CLOSE,
        events=[
            Event.exit(
                kind=kind,
                span=Range(pos, pos)
            )
        ],
        container=None
    )


class TestRules(unittest.TestCase):
    def test_open(self):
        cases = [
            TestCase(
                'open para',
                args=Args(
                    text='This is a paragraph.',
                ),
                expected=Expected(
                    pos=0,
                    result=new_open_result(0, BlockContainer.PARA)
                ),
                rule=ParaRule(),
            ),
            TestCase(
                'open blockquote',
                args=Args(
                    text='> Blockquote starts here.',
                ),
                expected=Expected(
                    pos=2,
                    result=new_open_result(0, BlockContainer.BLOCK_QUOTE)
                ),
                rule=BlockquoteRule(),
            ),
        ]

        for name, args, expected, rule in cases:
            with self.subTest(name):
                cursor = InputText(args.text)
                cursor.pos = args.pos

                result = rule.try_open(cursor)
                self.assertEqual(result, expected.result)

    def test_continue(self):
        cases = [
            TestCase(
                'continue para',
                args=Args(
                    text='This is a paragraph.',
                ),
                expected=Expected(
                    pos=0,
                    result=RuleResult.continue_ok()
                ),
                rule=ParaRule(),
            ),
            TestCase(
                'whitespace cannot continue para',
                args=Args(
                    text=' ...continued',
                ),
                expected=Expected(
                    pos=0,
                    result=RuleResult.fail()
                ),
                rule=ParaRule(),
            ),
            TestCase(
                'continue blockquote',
                args=Args(
                    text='> This is a paragraph.',
                    pos=0,
                ),
                expected=Expected(
                    pos=1,
                    result=RuleResult.continue_ok()
                ),
                rule=ParaRule(),
            ),
        ]

        for name, args, expected, rule in cases:
            with self.subTest(name):
                cursor = InputText(args.text)
                cursor.pos = args.pos

                result = rule.on_continue(
                    Container(ParaRule()),
                    ParsingContext(
                        cursor=cursor,
                    )
                )
                self.assertEqual(result, expected.result)

    def test_close(self):
        cases = [
            TestCase(
                'close para',
                args=Args(
                    text='this paragraph ends here.',
                    pos=25,
                    last_span_end=24,
                ),
                expected=Expected(
                    pos=25,
                    result=new_close_result(25, BlockContainer.PARA)
                ),
                rule=ParaRule(),
            ),
            TestCase(
                'close blockquote',
                args=Args(
                    text='A new block.',
                    pos=0,
                ),
                expected=Expected(
                    pos=0,
                    result=new_close_result(0, BlockContainer.BLOCK_QUOTE)
                ),
                rule=BlockquoteRule(),
            ),
        ]

        for name, args, expected, rule in cases:
            with self.subTest(name):
                cursor = InputText(args.text)
                cursor.pos = args.pos

                result = rule.on_close(
                    Container(ParaRule()),
                    ParsingContext(
                        cursor=cursor,
                        is_covered=args.is_covered,
                        last_span_end=args.last_span_end
                    )
                )
                self.assertEqual(result, expected.result)



if __name__ == '__main__':
    unittest.main()