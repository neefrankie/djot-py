from dataclasses import dataclass
from typing import List, Tuple
import unittest

from djot.event import (
    Event,
    InlineLeaf,
    VerbatimKind,
    Action,
)
from djot.inline.state import InlineState
from djot.input import InputText
from djot.options import Options
from djot.inline.backslash import BackslashMatcher
from djot.inline.backtick import BacktickMatcher
from djot.common import Range

@dataclass
class TestData:
    text: str
    args: Tuple[int, int]
    fixture: List[Event]
    expected_pos: int
    expected_events: List[Event]

class TestMatcher(unittest.TestCase):
    def test_bachslash(self):
        cases = [
            (
                '\\  \n',
                4,
                [
                    Event.new(0, 0, InlineLeaf.ESCAPE),
                    Event.new(1, 3, InlineLeaf.HARD_BREAK),
                ]
            ),
            (
                '\\!',
                2,
                [
                    Event.new(0, 0, InlineLeaf.ESCAPE),
                    Event.new(1, 1, InlineLeaf.STR),
                ]
            ),
            (
                '\\ ',
                2,
                [
                    Event.new(0, 0, InlineLeaf.ESCAPE),
                    Event.new(1, 1, InlineLeaf.NBSP),
                ]
            )
        ]

        for text, expected_pos, expected_events in cases:
            state = InlineState(InputText(text), Options())
            matcher = BackslashMatcher()
            actual_pos = matcher(state, 0, len(text)-1)
            self.assertEqual(actual_pos, expected_pos)
            self.assertEqual(state.events, expected_events)

    def test_backtick(self):
        cases = [
            TestData(
                text='$$`',
                args=(2, 2),
                fixture=[
                    Event.new(0, 0, InlineLeaf.STR),
                    Event.new(1, 2, InlineLeaf.STR)
                ],
                expected_pos=3,
                expected_events=[
                    Event.enter(Range(0, 2), VerbatimKind.DISPLAY_MATH),
                ]
            ),
            TestData(
                text='$`',
                args=(1, 1),
                fixture=[
                    Event.new(0, 0, InlineLeaf.STR),
                ],
                expected_pos=2,
                expected_events=[
                    Event.enter(Range(0, 1), VerbatimKind.INLINE_MATH),
                ]
            ),
            TestData(
                text='`',
                args=(0, 0),
                fixture=[],
                expected_pos=1,
                expected_events=[
                    Event.enter(Range(0, 0), VerbatimKind.VERBATIM),
                ]
            )
        ]

        for c in cases:
            with self.subTest(c.text):
                state = InlineState(InputText(c.text), Options())
                state.events.extend(c.fixture)
                matcher = BacktickMatcher()
                actual_pos = matcher(state, c.args[0], c.args[1])
                self.assertEqual(actual_pos, c.expected_pos)
                self.assertEqual(state.events, c.expected_events)



if __name__ == '__main__':
    unittest.main()