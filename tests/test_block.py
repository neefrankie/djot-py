from typing import Dict, List, NamedTuple, Optional
import unittest

from djot.common import Range
from djot.event import (
    Event,
    BlockContainer,
    InlineContainer,
    VerbatimKind,
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
    def test_paragraphs(self):

        text = "hello *world*\n\nfoo"

        expected = [
            Event.para(0, 0),
            Event.str(0, 5),
            Event.strong(6, 6),
            Event.str(7, 11),
            Event.strong(12, 12, False),
            Event.para(13, 13, False),
            Event.blankline(14, 14),
            Event.para(15, 15),
            Event.str(15, 17),
            Event.para(18, 18, False),
        ]

        parser = EventParser(text)
        events = list(parser.parse())
        self.assertEqual(events, expected)


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