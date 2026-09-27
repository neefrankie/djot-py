from typing import List, NamedTuple
import unittest

from djot.event import (
    Event,
    InlineLeaf,
    VerbatimKind,
    InlineContainer,
)
from djot.common import Range
from djot.inline.state import InlineState, OpenerKind, OpenerV2
from djot.input import InputText
from djot.options import Options
from djot.inline.backslash import BackslashMatcher
from djot.inline.backtick import BacktickMatcher
from djot.inline.brace_left import LeftBraceMatcher
from djot.inline.bracket_left import LeftBracketMatcher
from djot.inline.bracket_right import RightBracketMatcher
from djot.inline.colon import ColonMatcher
from djot.inline.lessthan import LessthanMatcher
from djot.inline.paren_left import LeftParenMatcher
from djot.inline.paren_right import RightParenMatcher
from djot.inline.period import PeriodMatcher
from djot.inline.between import (
    MatchContext,
    DelimiterCap,
    MarkerStyle,
    determine_bare_context,
    determine_brace_context,
    SubscriptMatcher,
    SuperscriptMatcher,
    EmphMatcher,
    StrongMatcher,
    InsertMatcher,
    MarkMatcher,
    SingleQuoteMatcher,
    DoubleQuoteMatcher,
)
from djot.inline.hyphen import HyphenMatcher

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

def new_state(
    text: str,
    dest: bool = False,
    events: List[Event] | None = None,
):
    state = InlineState(InputText(text), Options())
    state.destination = dest

    if events:
        state.events = events

    return state


def new_closer_state(
    text: str,
    open_span: Range,
    open_token: str = '[',
    close_span: Range | None = None,
    image_span: Range | None = None,
    kind: OpenerKind = OpenerKind.REFERENCE_LINK,
):

    state = InlineState(InputText(text), Options())

    if image_span:
        state.push_event(
            Event.leaf(image_span, InlineLeaf.STR)
        )
    
    opener = state.add_opener(open_token, Event.leaf(open_span, InlineLeaf.STR))

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

        if kind == OpenerKind.EXPLICIT_LINK:
            state.destination = True

    return state


class TestMatcher(unittest.TestCase):
    def test_backslash(self):
        cases = [
            TestCase(
                'hard break',
                Args(
                    state=new_state('\\  \n'),
                    pos=0,
                    endpos=3
                ),
                Expected(
                    pos=4,
                    events=[
                        Event.new(0, 0, InlineLeaf.ESCAPE),
                        Event.new(1, 3, InlineLeaf.HARD_BREAK),
                    ]
                )
            ),
            TestCase(
                'escape',
                Args(
                    state=new_state('\\!'),
                    pos=0,
                    endpos=1,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.new(0, 0, InlineLeaf.ESCAPE),
                        Event.new(1, 1, InlineLeaf.STR),
                    ]
                )
            ),
            TestCase(
                'non-breaking space',
                Args(
                    state=new_state('\\ '),
                    pos=0,
                    endpos=1,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.new(0, 0, InlineLeaf.ESCAPE),
                        Event.new(1, 1, InlineLeaf.NBSP),
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(name):
                matcher = BackslashMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_backtick(self):
        cases = [
            TestCase(
                'display math',
                Args(
                    state=new_state('$$`', events=[
                        Event.new(0, 0, InlineLeaf.STR),
                        Event.new(1, 2, InlineLeaf.STR)
                    ]),
                    pos=2,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.enter(Range(0, 2), VerbatimKind.DISPLAY_MATH),
                    ]
                )
            ),
            TestCase(
                'inline math',
                Args(
                    state=new_state('$`', events=[
                        Event.new(0, 0, InlineLeaf.STR),
                    ]),
                    pos=1,
                    endpos=1,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.enter(Range(0, 1), VerbatimKind.INLINE_MATH),
                    ]
                )
            ),
            TestCase(
                'verbatim',
                Args(
                    state=new_state('`'),
                    pos=0,
                    endpos=0,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.enter(Range(0, 0), VerbatimKind.VERBATIM),
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(name):
                matcher = BacktickMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_left_brace(self):
        cases = [
            TestCase(
                '{_italic_}',
                Args(
                    state=new_state('{_italic_}'),
                    pos=0,
                    endpos=7,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.new(0, 0, InlineLeaf.OPEN_MARKER)
                    ]
                )
            ),
            TestCase(
                '{#ident}',
                Args(
                    state=new_state('{#ident}'),
                    pos=0,
                    endpos=6,
                ),
                Expected(
                    pos=0,
                    events=[]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = LeftBraceMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_left_bracket(self):
        cases = [
            TestCase(
                'footnote reference',
                Args(
                    state=new_state('[^foo]'),
                    pos=0,
                    endpos=5,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.new(0, 0, InlineLeaf.STR)
                    ]
                )
            ),
            TestCase(
                '[foo]',
                Args(
                    state=new_state('[foo]'),
                    pos=0,
                    endpos=4,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.new(0, 0, InlineLeaf.STR)
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = LeftBracketMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_right_bracket(self):
        cases = [
            TestCase(
                '_commit_note_reference',
                Args(
                    state=new_closer_state(
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
                    new_closer_state(
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
                    new_closer_state(
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
                    state=new_closer_state(
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
                    state=new_closer_state(
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
                    state=new_closer_state(
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

    def test_colon(self):
        smiley = ':smiley:'
        strcolon = ': foo'
        cases = [
            TestCase(
                'symbol',
                Args(
                    state=InlineState(InputText(smiley), Options()),
                    pos=0,
                    endpos=len(smiley)-1
                ),
                Expected(
                    pos=len(smiley),
                    events=[
                        Event.leaf(Range(0, len(smiley)-1), InlineLeaf.SYMBOL),
                    ]
                )
            ),
            TestCase(
                'str colon',
                Args(
                    state=InlineState(InputText(strcolon), Options()),
                    pos=0,
                    endpos=len(strcolon)-1
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.STR),
                    ]
                )
            ),
        ]
        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = ColonMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_lessthan(self):
        email = '<foo@bar.com>'
        url = '<https://example.com>'
        cases = [
            TestCase(
                'email',
                Args(
                    state=new_state(email),
                    pos=0,
                    endpos=len(email)-1
                ),
                Expected(
                    pos=len(email),
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.EMAIL),
                        Event.leaf(Range(1, len(email)-2), InlineLeaf.STR),
                        Event.exit(Range(len(email)-1, len(email)-1), InlineContainer.EMAIL)
                    ]
                )
            ),
            TestCase(
                'url',
                Args(
                    state=new_state(url),
                    pos=0,
                    endpos=len(url)-1
                ),
                Expected(
                    pos=len(url),
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.URL),
                        Event.leaf(Range(1, len(url)-2), InlineLeaf.STR),
                        Event.exit(Range(len(url)-1, len(url)-1), InlineContainer.URL)
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = LessthanMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_paren(self):
        paren = '(hello)'
        
        cases = [
            TestCase(
                'paren',
                Args(
                    state=new_state(paren, dest=True),
                    pos=0,
                    endpos=len(paren)-1
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0),
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = LeftParenMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_right_paren(self):
        cases = [
            TestCase(
                'commit link',
                Args(
                    new_closer_state(
                        text='[Text](foo)',
                        open_span=Range(0, 0),
                        close_span=Range(5, 5),
                        kind=OpenerKind.EXPLICIT_LINK,
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
                            InlineContainer.DESTINATION,
                        ),
                        Event.exit(
                            Range(10, 10),
                            InlineContainer.DESTINATION,
                        )
                    ],
                    dest=False
                )
            ),
            TestCase(
                'commit image',
                Args(
                    new_closer_state(
                        text='![Cat](cat)',
                        image_span=Range(0, 0),
                        open_span=Range(1, 1),
                        close_span=Range(5, 5),
                        kind=OpenerKind.EXPLICIT_LINK,
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
                            InlineContainer.DESTINATION,
                        ),
                        Event.exit(
                            Range(10, 10),
                            InlineContainer.DESTINATION,
                        )
                    ],
                    dest=False,
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = RightParenMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)
                self.assertEqual(args.state.destination, expected.dest)

    def test_period(self):
        cases = [
            TestCase(
                'period',
                Args(
                    state=new_state('...'),
                    pos=0,
                    endpos=2
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.leaf(
                            Range(0, 2),
                            InlineLeaf.ELLIPSES,
                        )
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = PeriodMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_subscript(self):
        cases = [
            TestCase(
                'subscript open',
                Args(
                    state=new_state('H~2~O'),
                    pos=1,
                    endpos=5,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.str(1, 1)
                    ]
                )
            ),
            TestCase(
                'subscript close',
                Args(
                    state=new_closer_state(
                        'H~2~O',
                        open_span=Range(1, 1),
                        open_token='~'
                    ),
                    pos=3,
                    endpos=5,
                ),
                Expected(
                    pos=4,
                    events=[
                        Event.enter(Range(1, 1), InlineContainer.SUBSCRIPT),
                        Event.exit(Range(3, 3), InlineContainer.SUBSCRIPT)
                    ]
                )
            ),
            TestCase(
                'braced subscript open',
                Args(
                    state=new_state(
                        'H{~2~}O',
                        events=[
                            Event.leaf(Range(1, 1), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=2,
                    endpos=7,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.leaf(Range(1, 1), InlineLeaf.OPEN_MARKER),
                        Event.str(1, 2)
                    ]
                )
            ),
            TestCase(
                'braced subscript close',
                Args(
                    state=new_closer_state(
                        'H{~2~}O',
                        open_span=Range(1, 2),
                        open_token='{~'
                    ),
                    pos=4,
                    endpos=7,
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.enter(Range(1, 2), InlineContainer.SUBSCRIPT),
                        Event.exit(Range(4, 5), InlineContainer.SUBSCRIPT)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = SubscriptMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_superscript(self):
        cases = [
            TestCase(
                'superscript open',
                Args(
                    state=new_state('^TM^'),
                    pos=0,
                    endpos=4,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0)
                    ]
                )
            ),
            TestCase(
                'superscript close',
                Args(
                    state=new_closer_state(
                        '^TM^',
                        open_span=Range(0, 0),
                        open_token='^'
                    ),
                    pos=3,
                    endpos=3,
                ),
                Expected(
                    pos=4,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.SUPERSCRIPT),
                        Event.exit(Range(3, 3), InlineContainer.SUPERSCRIPT)
                    ]
                )
            ),
            TestCase(
                'braced superscript open',
                Args(
                    state=new_state(
                        '{^TM^}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    endpos=5,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                )
            ),
            TestCase(
                'braced subscript close',
                Args(
                    state=new_closer_state(
                        '{^TM^}',
                        open_span=Range(0, 1),
                        open_token='{^'
                    ),
                    pos=4,
                    endpos=5,
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.SUPERSCRIPT),
                        Event.exit(Range(4, 5), InlineContainer.SUPERSCRIPT)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = SuperscriptMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_emphasis(self):
        cases = [
            TestCase(
                'emphasis open',
                Args(
                    state=new_state('_e_'),
                    pos=0,
                    endpos=2,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0)
                    ]
                )
            ),
            TestCase(
                'emphasis close',
                Args(
                    state=new_closer_state(
                        '_emph_',
                        open_span=Range(0, 0),
                        open_token='_'
                    ),
                    pos=5,
                    endpos=5,
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.EMPH),
                        Event.exit(Range(5, 5), InlineContainer.EMPH)
                    ]
                )
            ),
            TestCase(
                'braced emphasis open',
                Args(
                    state=new_state(
                        '{_emph_}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    endpos=7,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                )
            ),
            TestCase(
                'braced emphasis close',
                Args(
                    state=new_closer_state(
                        '{_emph_}',
                        open_span=Range(0, 1),
                        open_token='{_'
                    ),
                    pos=6,
                    endpos=7,
                ),
                Expected(
                    pos=8,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.EMPH),
                        Event.exit(Range(6, 7), InlineContainer.EMPH)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = EmphMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_strong(self):
        cases = [
            TestCase(
                'strong open',
                Args(
                    state=new_state('*a*'),
                    pos=0,
                    endpos=2,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0)
                    ]
                )
            ),
            TestCase(
                'strong close',
                Args(
                    state=new_closer_state(
                        '*a*',
                        open_span=Range(0, 0),
                        open_token='*'
                    ),
                    pos=2,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.STRONG),
                        Event.exit(Range(2, 2), InlineContainer.STRONG)
                    ]
                )
            ),
            TestCase(
                'braced strong open',
                Args(
                    state=new_state(
                        '{*a*}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                )
            ),
            TestCase(
                'braced strong close',
                Args(
                    state=new_closer_state(
                        '{*a*}',
                        open_span=Range(0, 1),
                        open_token='{*'
                    ),
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.STRONG),
                        Event.exit(Range(3, 4), InlineContainer.STRONG)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = StrongMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_insert(self):
        cases = [
            TestCase(
                'insert open',
                Args(
                    state=new_state(
                        '{+a+}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                )
            ),
            TestCase(
                'insert close',
                Args(
                    state=new_closer_state(
                        '{+a+}',
                        open_span=Range(0, 1),
                        open_token='{+'
                    ),
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.INSERT),
                        Event.exit(Range(3, 4), InlineContainer.INSERT)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = InsertMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)
    
    def test_hyphen(self):
        cases = [
            TestCase(
                'delete open',
                Args(
                    state=new_state(
                        '{-a-}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                )
            ),
            TestCase(
                'delete close',
                Args(
                    state=new_closer_state(
                        '{-a-}',
                        open_span=Range(0, 1),
                        open_token='{-'
                    ),
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.DELETE),
                        Event.exit(Range(3, 4), InlineContainer.DELETE)
                    ]
                )
            ),
            TestCase(
                'dash brace',
                Args(
                    state=new_state('-}'),
                    pos=0,
                    endpos=1,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.str(0, 1)
                    ]
                )
            ),
            TestCase(
                'em dash',
                Args(
                    state=new_state('---'),
                    pos=0,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.leaf(Range(0, 2), InlineLeaf.EM_DASH)
                    ]
                )
            ),
            TestCase(
                'en dash',
                Args(
                    state=new_state('--'),
                    pos=0,
                    endpos=1,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 1), InlineLeaf.EN_DASH)
                    ]
                )
            ),
            TestCase(
                'en dash',
                Args(
                    state=new_state('-----'),
                    pos=0,
                    endpos=1,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.leaf(Range(0, 2), InlineLeaf.EM_DASH),
                        Event.leaf(Range(3, 4), InlineLeaf.EN_DASH)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = HyphenMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_mark(self):
        cases = [
            TestCase(
                'mark open',
                Args(
                    state=new_state(
                        '{=a=}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                )
            ),
            TestCase(
                'mark close',
                Args(
                    state=new_closer_state(
                        '{=a=}',
                        open_span=Range(0, 1),
                        open_token='{='
                    ),
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.MARK),
                        Event.exit(Range(3, 4), InlineContainer.MARK)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = MarkMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_single_quote(self):
        cases = [
            TestCase(
                'left single quote',
                Args(
                    state=new_state("'a'"),
                    pos=0,
                    endpos=2,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.RIGHT_SINGLE_QUOTE)
                    ]
                )
            ),
            TestCase(
                'right double quote',
                Args(
                    state=new_closer_state(
                        "'a'",
                        open_span=Range(0, 0),
                        open_token="'"
                    ),
                    pos=2,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.SINGLE_QUOTED),
                        Event.exit(Range(2, 2), InlineContainer.SINGLE_QUOTED)
                    ]
                )
            ),
            TestCase(
                'braced left single quote',
                Args(
                    state=new_state(
                        "{'a'}",
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.leaf(Range(0, 1), InlineLeaf.LEFT_SINGLE_QUOTE)
                    ]
                )
            ),
            TestCase(
                'braced right single quote',
                Args(
                    state=new_closer_state(
                        "{'a'}",
                        open_span=Range(0, 1),
                        open_token="{'"
                    ),
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.SINGLE_QUOTED),
                        Event.exit(Range(3, 4), InlineContainer.SINGLE_QUOTED)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = SingleQuoteMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_double_quote(self):
        cases = [
            TestCase(
                'left double quote',
                Args(
                    state=new_state('"a"'),
                    pos=0,
                    endpos=2,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.LEFT_DOUBLE_QUOTE)
                    ]
                )
            ),
            TestCase(
                'right double quote',
                Args(
                    state=new_closer_state(
                        '"a"',
                        open_span=Range(0, 0),
                        open_token='"'
                    ),
                    pos=2,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.DOUBLE_QUOTED),
                        Event.exit(Range(2, 2), InlineContainer.DOUBLE_QUOTED)
                    ]
                )
            ),
            TestCase(
                'braced left double quote',
                Args(
                    state=new_state(
                        '{"a"}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.leaf(Range(0, 1), InlineLeaf.LEFT_DOUBLE_QUOTE)
                    ]
                )
            ),
            TestCase(
                'braced right double quote',
                Args(
                    state=new_closer_state(
                        '{"a"}',
                        open_span=Range(0, 1),
                        open_token='{"'
                    ),
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.DOUBLE_QUOTED),
                        Event.exit(Range(3, 4), InlineContainer.DOUBLE_QUOTED)
                    ]
                )
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = DoubleQuoteMatcher()
                actual_pos = matcher(args.state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(args.state.events, expected.events)


class OCArgs(NamedTuple):
    state: InlineState
    pos: int
    ctx: MatchContext
    opener: OpenerV2 | None = None

class BareArgs(NamedTuple):
    cursor: InputText
    current_pos: int
    can_open: bool

class BraceArgs(NamedTuple):
    cursor: InputText
    current_pos: int
    endpos: int
    last_event: Event | None

class TestBetweenMatcher(unittest.TestCase):
    def test_bare_context(self):
        cases = [
            (
                'bare open',
                BareArgs(
                    cursor=InputText('*bold*'),
                    current_pos=0,
                    can_open=True
                ),
                MatchContext(
                    delimiter_cap=DelimiterCap.NONE | DelimiterCap.CAN_OPEN,
                    token_start=0,
                    token_end=0,
                    marker_style=MarkerStyle.NONE
                ),
            ),
            (
                'bare close',
                BareArgs(
                    cursor=InputText('*bold*'),
                    current_pos=5,
                    can_open=True,
                ),
                MatchContext(
                    delimiter_cap=DelimiterCap.NONE | DelimiterCap.CAN_CLOSE,
                    token_start=5,
                    token_end=5,
                    marker_style=MarkerStyle.NONE
                ),
            ),
            (
                'bare open close',
                BareArgs(
                    cursor=InputText('a*b'),
                    current_pos=1,
                    can_open=True
                ),
                MatchContext(
                    delimiter_cap=DelimiterCap.NONE | DelimiterCap.CAN_CLOSE | DelimiterCap.CAN_OPEN,
                    token_start=1,
                    token_end=1,
                    marker_style=MarkerStyle.NONE
                ),
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.cursor.src}'):
                actual = determine_bare_context(
                    args.cursor,
                    args.current_pos,
                    args.can_open
                )
                self.assertEqual(actual, expected)

    def test_brace_context(self):
        cases = [
            (
                'brace open',
                BraceArgs(
                    cursor=InputText('{*bold*}'),
                    current_pos=1,
                    endpos=7,
                    last_event=Event.leaf(
                        Range(0, 0), 
                        InlineLeaf.OPEN_MARKER
                    )
                ),
                MatchContext(
                    delimiter_cap=DelimiterCap.CAN_OPEN,
                    token_start=0,
                    token_end=1,
                    marker_style=MarkerStyle.OPEN
                ),
            ),
            (
                'brace close',
                BraceArgs(
                    cursor=InputText('{*bold*}'),
                    current_pos=6,
                    endpos=7,
                    last_event=None
                ),
                MatchContext(
                    delimiter_cap=DelimiterCap.CAN_CLOSE,
                    token_start=6,
                    token_end=7,
                    marker_style=MarkerStyle.CLOSE
                ),
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.cursor.src}'):
                actual = determine_brace_context(
                    args.cursor,
                    args.current_pos,
                    args.endpos,
                    args.last_event
                )
                self.assertEqual(actual, expected)

    def test_handle_opener(self):
        cases = [
            (
                'handle opener',
                OCArgs(
                    state=new_state('*bold*'),
                    pos=0,
                    ctx=MatchContext(
                        delimiter_cap=DelimiterCap.CAN_OPEN,
                        token_start=0,
                        token_end=0,
                        marker_style=MarkerStyle.NONE
                    )
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0)
                    ]
                ),
            ),
            (
                'handle brace opener',
                OCArgs(
                    state=new_state(
                        '{*bold*}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER)
                        ]
                    ),
                    pos=1,
                    ctx=MatchContext(
                        delimiter_cap=DelimiterCap.CAN_OPEN,
                        token_start=0,
                        token_end=1,
                        marker_style=MarkerStyle.OPEN
                    )
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ],
                ),
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                matcher = StrongMatcher()
                actual = matcher._handle_opener(
                    args.state,
                    args.pos,
                    args.ctx,
                )
                self.assertEqual(actual, expected.pos)
                self.assertEqual(args.state.events, expected.events)

    def test_handle_closer(self):
        cases = [
            (
                'handle closer',
                OCArgs(
                    state=new_state('*bold*', events=[
                        Event.str(0, 0)
                    ]),
                    pos=5,
                    ctx=MatchContext(
                        delimiter_cap=DelimiterCap.CAN_CLOSE,
                        token_start=5,
                        token_end=5,
                        marker_style=MarkerStyle.NONE
                    ),
                    opener=OpenerV2.new(Event.str(0, 0), 0),
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.STRONG),
                        Event.exit(Range(5, 5), InlineContainer.STRONG)
                    ]
                ),

            ),
            (
                'handle brace closer',
                OCArgs(
                    state=new_state(
                        '{*bold*}',
                        events=[
                            Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                            Event.leaf(Range(0, 1), InlineLeaf.STR)
                        ]
                    ),
                    pos=6,
                    ctx=MatchContext(
                        delimiter_cap=DelimiterCap.CAN_CLOSE,
                        token_start=6,
                        token_end=7,
                        marker_style=MarkerStyle.CLOSE,
                    ),
                    opener=OpenerV2.new(Event.str(0, 1), 1),
                ),
                Expected(
                    pos=8,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.enter(Range(0, 1), InlineContainer.STRONG),
                        Event.exit(Range(6, 7), InlineContainer.STRONG)
                    ],
                ),
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.state.cursor.src}'):
                assert args.opener is not None
                matcher = StrongMatcher()
                actual = matcher._handle_closer(
                    state=args.state,
                    ctx=args.ctx,
                    pos=args.pos,
                    opener=args.opener
                )
                self.assertEqual(actual, expected.pos)
                self.assertEqual(args.state.events, expected.events)


if __name__ == '__main__':
    unittest.main()