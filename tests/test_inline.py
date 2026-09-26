from dataclasses import dataclass
from typing import List, NamedTuple, Tuple
import unittest

from djot.event import (
    Event,
    InlineLeaf,
    VerbatimKind,
    InlineContainer,
)
from djot.common import Range
from djot.inline.state import InlineState, OpenerKind
from djot.input import InputText
from djot.options import Options
from djot.inline.backslash import BackslashMatcher
from djot.inline.backtick import BacktickMatcher
from djot.inline.brace_left import LeftBraceMatcher
from djot.inline.bracket_left import LeftBracketMatcher
from djot.inline.bracket_right import RightBracketMatcher

@dataclass
class TestData:
    text: str
    args: Tuple[int, int]
    fixture: List[Event]
    expected_pos: int
    expected_events: List[Event]

class Args(NamedTuple):
    state: InlineState
    pos: int
    endpos: int

class Expected(NamedTuple):
    pos: int
    events: List[Event]
    dest: bool = False

class TestCase(NamedTuple):
    name: str
    args: Args
    expected: Expected


def new_link_state(
    text: str,
    open_span: Range,
    close_span: Range | None = None,
    image_span: Range | None = None,
    kind: OpenerKind = OpenerKind.REFERENCE_LINK,
):

    state = InlineState(InputText(text), Options())

    if image_span:
        state.push_event(
            Event.leaf(image_span, InlineLeaf.STR)
        )
    
    opener = state.add_opener('[', Event.leaf(open_span, InlineLeaf.STR))

    if close_span:
        opener.set_first_closer(
            state.add_candidate_event(
                Event.leaf(close_span, InlineLeaf.STR)
            )
        )

        opener.set_second_opener(
            state.add_candidate_event(
                Event.leaf(
                    Range(close_span.end+1, close_span.end+1),
                    InlineLeaf.STR
                )
            ),
            kind=kind,
        )

    return state


class TestMatcher(unittest.TestCase):
    def test_backslash(self):
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
            with self.subTest(text):
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

    def test_left_brace(self):
        cases = [
            (
                '{_italic_}',
                1,
                [
                    Event.new(0, 0, InlineLeaf.OPEN_MARKER)
                ]
            ),
            (
                '{#ident}',
                0,
                []

            )
        ]

        for text, expected_pos, expected_events in cases:
            with self.subTest(text):
                state = InlineState(InputText(text), Options())
                matcher = LeftBraceMatcher()
                actual_pos = matcher(state, 0, len(text)-1)
                self.assertEqual(actual_pos, expected_pos)
                self.assertEqual(state.events, expected_events)

    def test_left_bracket(self):
        cases = [
            (
                '[^foo]',
                1,
                [
                    Event.new(0, 0, InlineLeaf.STR)
                ]
            ),
            (
                '[foo]',
                1,
                [
                    Event.new(0, 0, InlineLeaf.STR)
                ]
            )
        ]

        for text, expected_pos, expected_events in cases:
            with self.subTest(text):
                state = InlineState(InputText(text), Options())
                matcher = LeftBracketMatcher()
                actual_pos = matcher(state, 0, len(text)-1)
                self.assertEqual(actual_pos, expected_pos)
                self.assertEqual(state.events, expected_events)

    def test_right_bracket(self):
        cases = [
            TestCase(
                '_commit_note_reference',
                Args(
                    state=new_link_state(
                        text='[^foo]',
                        open_span=Range(0, 0),
                    ),
                    pos=5,
                    endpos=5,
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.leaf(
                            Range(0, 5),
                            InlineLeaf.FOOTNOTE_REF,
                        )
                    ]
                )
            ),
            TestCase(
                '_commit_link',
                Args(
                    new_link_state(
                        text='[Text][foo]',
                        open_span=Range(0, 0),
                        close_span=Range(5, 5),
                        kind=OpenerKind.REFERENCE_LINK,
                    ),
                    pos=10,
                    endpos=len('[Text][foo]')-1
                ),
                Expected(
                    pos=11,
                    events=[
                        Event.enter( # [
                            Range(0, 0),
                            InlineContainer.LINK_TEXT,
                        ),
                        Event.exit( # ]
                            Range(5, 5),
                            InlineContainer.LINK_TEXT,
                        ),
                        Event.enter( # [
                            Range(6, 6),
                            InlineContainer.REFERENCE,
                        ),
                        Event.exit(
                            Range(10, 10),
                            InlineContainer.REFERENCE,
                        )
                    ]
                )
            ),
            TestCase(
                '_commit_image',
                Args(
                    new_link_state(
                        text='![Cat][cat]',
                        image_span=Range(0, 0),
                        open_span=Range(1, 1),
                        close_span=Range(5, 5),
                        kind=OpenerKind.REFERENCE_LINK,
                    ),
                    pos=10,
                    endpos=len('![Cat][foo]')-1
                ),
                Expected(
                    pos=11,
                    events=[
                        Event.leaf(
                            Range(0, 0),
                            InlineLeaf.IMAGE_MARKER,
                        ),
                        Event.enter( # [
                            Range(1, 1),
                            InlineContainer.IMAGE_TEXT,
                        ),
                        Event.exit( # ]
                            Range(5, 5),
                            InlineContainer.IMAGE_TEXT,
                        ),
                        Event.enter( # [
                            Range(6, 6),
                            InlineContainer.REFERENCE,
                        ),
                        Event.exit(
                            Range(10, 10),
                            InlineContainer.REFERENCE,
                        )
                    ]
                )
            ),
            TestCase(
                'prepare reference link',
                Args(
                    state=new_link_state(
                        text='[Foo][bar]',
                        open_span=Range(0, 0),
                    ),
                    pos=4,
                    endpos=len('[Foo][bar]')-1
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.STR),
                        Event.leaf(Range(4, 4), InlineLeaf.STR),
                        Event.leaf(Range(5, 5), InlineLeaf.STR),
                    ]
                )
            ),
            TestCase(
                'prepare explicit link',
                Args(
                    state=new_link_state(
                        text='[Foo](bar)',
                        open_span=Range(0, 0),
                    ),
                    pos=4,
                    endpos=len('[Foo][bar]')-1
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.STR),
                        Event.leaf(Range(4, 4), InlineLeaf.STR),
                        Event.leaf(Range(5, 5), InlineLeaf.STR),
                    ],
                    dest=True,
                ),
            ),
            TestCase(
                'prepare span',
                Args(
                    state=new_link_state(
                        text='[Foo]{#bar}',
                        open_span=Range(0, 0),
                    ),
                    pos=4,
                    endpos=len('[Foo]{#bar}')-1
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.SPAN),
                        Event.exit(Range(4, 4), InlineContainer.SPAN),
                    ],
                ),
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = RightBracketMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)
                self.assertEqual(args.state.destination, expected.dest)



if __name__ == '__main__':
    unittest.main()