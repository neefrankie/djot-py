from typing import List, NamedTuple
import unittest

from djot.event import (
    Event,
    InlineLeaf,
    VerbatimKind,
    InlineContainer,
    AttrKind,
    BlockContainer,
    VerbatimKind,
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
from djot.inline.parser import InlineParser

class Args(NamedTuple):
    text: str
    pos: int
    endpos: int
    ctx: MatchContext | None = None

class Expected(NamedTuple):
    pos: int
    events: List[Event]
    dest: bool = False

class VerbArgs(NamedTuple):
    len: int = 0
    typ: VerbatimKind = VerbatimKind.VERBATIM
    events: List[Event] | None = None # for $$

def populate_verb_state(state: InlineState, args: VerbArgs):
    state.verbatim_len = args.len
    state.verbatim_type = args.typ

    if args.events:
        state.extend_events(args.events)

    return state

class LinkArgs(NamedTuple):
    open_span: Range
    open_token: str = '['
    close_span: Range | None = None
    image_span: Range | None = None
    kind: OpenerKind = OpenerKind.REFERENCE_LINK

def populate_link_state(state: InlineState, args: LinkArgs):
    if args.image_span:
        state.push_event(
            Event.leaf(args.image_span, InlineLeaf.STR)
        )
    
    opener = state.add_opener(
        args.open_token,
        Event.leaf(args.open_span, InlineLeaf.STR)
    )

    if args.close_span:
        opener.set_first_closer(
            state.add_candidate_event(
                Event.leaf(args.close_span, InlineLeaf.STR)
            )
        )

        opener.set_second_opener(
            state.add_candidate_event(
                Event.leaf(
                    Range(args.close_span.end+1, args.close_span.end+1),
                    InlineLeaf.STR
                )
            ),
            kind=args.kind,
        )

        if args.kind == OpenerKind.EXPLICIT_LINK:
            state.destination = True


    return state

class OpenerArgs(NamedTuple):
    start: int
    end: int
    token_name: str
    kind: InlineLeaf = InlineLeaf.STR

def populate_between_state(state: InlineState, args: OpenerArgs):
    
    # Mock steps in LeftBraceMatcher.
    # This step is required to determine `{*` is opening delimiter.
    # This is sort of a hack. It's not elegant.
    if args.token_name.startswith('{') and args.kind == InlineLeaf.OPEN_MARKER:
        state.push_event(
            Event.leaf(
                Range(args.start, args.start),
                InlineLeaf.OPEN_MARKER,
            )
        )
        return state
    
    # Mock steps in BetweenMatcher._handle_opener
    state.add_opener(
        name=args.token_name,
        default_event=Event.leaf(
            Range(args.start, args.end),
            args.kind,
        )
    )

    return state

class TestCase(NamedTuple):
    name: str
    args: Args
    expected: Expected
    pre_state: None | VerbArgs | LinkArgs | OpenerArgs = None

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
                    text='\\  \n',
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
                    text='\\!',
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
                    text='\\ ',
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

        for name, args, expected, _ in cases:
            with self.subTest(name):
                state = InlineState(InputText(args.text), Options())
                matcher = BackslashMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_backtick(self):
        cases = [
            TestCase(
                'display math',
                Args(
                    text='$$`',
                    pos=2,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.enter(Range(0, 2), VerbatimKind.DISPLAY_MATH),
                    ]
                ),
                VerbArgs(events=[
                    Event.new(0, 0, InlineLeaf.STR),
                    Event.new(1, 2, InlineLeaf.STR)
                ])
            ),
            TestCase(
                'inline math',
                Args(
                    text='$`',
                    pos=1,
                    endpos=1,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.enter(Range(0, 1), VerbatimKind.INLINE_MATH),
                    ]
                ),
                VerbArgs(events=[
                    Event.new(0, 0, InlineLeaf.STR),
                ])
            ),
            TestCase(
                'verbatim',
                Args(
                    text='`',
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

        for name, args, expected, state_args in cases:
            with self.subTest(name):
                state = InlineState(InputText(args.text), Options())
                if isinstance(state_args, VerbArgs):
                    populate_verb_state(state, state_args)
                matcher = BacktickMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_left_brace(self):
        cases = [
            TestCase(
                '{_italic_}',
                Args(
                    text='{_italic_}',
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
                    text='{#ident}',
                    pos=0,
                    endpos=6,
                ),
                Expected(
                    pos=0,
                    events=[]
                )
            )
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                matcher = LeftBraceMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_left_bracket(self):
        cases = [
            TestCase(
                'footnote reference',
                Args(
                    text='[^foo]',
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
                    text='[foo]',
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

        for name, args, expected, _ in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                matcher = LeftBracketMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_right_bracket(self):
        cases = [
            (
                'comment not reference',
                Args(
                    text='[^foo]',
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
                ),
                LinkArgs(
                    open_span=Range(0, 0),
                )
            ),
            (
                'commit link',
                Args(
                    text='[Text][foo]',
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
                ),
                LinkArgs(
                    open_span=Range(0, 0),
                    close_span=Range(5, 5),
                    kind=OpenerKind.REFERENCE_LINK,
                )
            ),
            (
                'commit image',
                Args(
                    text='![Cat][cat]',
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
                ),
                LinkArgs(
                    open_span=Range(1, 1),
                    image_span=Range(0, 0),
                    close_span=Range(5, 5),
                    kind=OpenerKind.REFERENCE_LINK,
                )
            ),
            (
                'prepare reference link',
                Args(
                    text='[Foo][bar]',
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
                ),
                LinkArgs(
                    open_span=Range(0, 0),
                ),
            ),
            (
                'prepare explicit link',
                Args(
                    text='[Foo](bar)',
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
                LinkArgs(
                    open_span=Range(0, 0),
                )
            ),
            (
                'prepare span',
                Args(
                    text='[Foo]{#bar}',
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
                LinkArgs(
                    open_span=Range(0, 0),
                )
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                matcher = RightBracketMatcher()
                state = InlineState(InputText(args.text), Options())
                populate_link_state(state, state_args)
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)
                self.assertEqual(state.destination, expected.dest)

    def test_colon(self):
        smiley = ':smiley:'
        strcolon = ': foo'
        cases = [
            (
                'symbol',
                Args(
                    text=smiley,
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
            (
                'str colon',
                Args(
                    text=strcolon,
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
            with self.subTest(f'{name}: {args.text}'):
                matcher = ColonMatcher()
                state=InlineState(InputText(args.text), Options())
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_lessthan(self):
        email = '<foo@bar.com>'
        url = '<https://example.com>'
        cases = [
            (
                'email',
                Args(
                    text=email,
                    
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
            (
                'url',
                Args(
                    text=url,
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
            with self.subTest(f'{name}: {args.text}'):
                matcher = LessthanMatcher()
                state=InlineState(InputText(args.text), Options())
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_paren(self):
        paren = '(hello)'
        
        cases = [
            (
                'paren',
                Args(
                    text=paren,
                    pos=0,
                    endpos=len(paren)-1
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0),
                    ]
                ),
            ),
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.text}'):
                state=InlineState(InputText(args.text), Options())
                state.destination = True
                matcher = LeftParenMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_right_paren(self):
        cases = [
            (
                'commit link',
                Args(
                    text='[Text](foo)',
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
                ),
                LinkArgs(
                    open_span=Range(0, 0),
                    close_span=Range(5, 5),
                    kind=OpenerKind.EXPLICIT_LINK,
                )
            ),
            (
                'commit image',
                Args(
                    text='![Cat](cat)',
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
                ),
                LinkArgs(
                    image_span=Range(0, 0),
                    open_span=Range(1, 1),
                    close_span=Range(5, 5),
                    kind=OpenerKind.EXPLICIT_LINK,
                )
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                populate_link_state(state, state_args)
                matcher = RightParenMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)
                self.assertEqual(state.destination, expected.dest)

    def test_period(self):
        cases = [
            (
                'period',
                Args(
                    text='...',
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
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                matcher = PeriodMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_subscript(self):
        cases = [
            (
                'subscript open',
                Args(
                    text='H~2~O',
                    pos=1,
                    endpos=5,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.str(1, 1)
                    ]
                ),
                None,
            ),
            (
                'subscript close',
                Args(
                    text='H~2~O',
                    pos=3,
                    endpos=5,
                ),
                Expected(
                    pos=4,
                    events=[
                        Event.enter(Range(1, 1), InlineContainer.SUBSCRIPT),
                        Event.exit(Range(3, 3), InlineContainer.SUBSCRIPT)
                    ]
                ),
                OpenerArgs(1, 1, '~')
            ),
            (
                'braced subscript open',
                Args(
                    text='H{~2~}O',
                    pos=2,
                    endpos=7,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.leaf(Range(1, 1), InlineLeaf.OPEN_MARKER),
                        Event.str(1, 2)
                    ]
                ),
                OpenerArgs(1, 1, '{~', InlineLeaf.OPEN_MARKER)
            ),
            (
                'braced subscript close',
                Args(
                    text='H{~2~}O',
                    pos=4,
                    endpos=7,
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.enter(Range(1, 2), InlineContainer.SUBSCRIPT),
                        Event.exit(Range(4, 5), InlineContainer.SUBSCRIPT)
                    ]
                ),
                OpenerArgs(1, 2, '{~')
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                if state_args:
                    populate_between_state(state, state_args)
                matcher = SubscriptMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_superscript(self):
        cases = [
            TestCase(
                'superscript open',
                Args(
                    text='^TM^',
                    pos=0,
                    endpos=4,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0)
                    ]
                ),
                None,
            ),
            TestCase(
                'superscript close',
                Args(
                    text='^TM^',
                    pos=3,
                    endpos=3,
                ),
                Expected(
                    pos=4,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.SUPERSCRIPT),
                        Event.exit(Range(3, 3), InlineContainer.SUPERSCRIPT)
                    ]
                ),
                OpenerArgs(0, 0, '^')
            ),
            TestCase(
                'braced superscript open',
                Args(
                    text='{^TM^}',
                    pos=1,
                    endpos=5,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                ),
                OpenerArgs(0, 0, '{^', InlineLeaf.OPEN_MARKER)
            ),
            TestCase(
                'braced subscript close',
                Args(
                    text='{^TM^}',
                    pos=4,
                    endpos=5,
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.SUPERSCRIPT),
                        Event.exit(Range(4, 5), InlineContainer.SUPERSCRIPT)
                    ]
                ),
                OpenerArgs(0, 1, '{^')
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                if isinstance(state_args, OpenerArgs):
                    populate_between_state(state, state_args)
                matcher = SuperscriptMatcher()
                
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_emphasis(self):
        cases = [
            TestCase(
                'emphasis open',
                Args(
                    text='_e_',
                    pos=0,
                    endpos=2,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0)
                    ]
                ),
                None,
            ),
            TestCase(
                'emphasis close',
                Args(
                    text='_emph_',
                    pos=5,
                    endpos=5,
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.EMPH),
                        Event.exit(Range(5, 5), InlineContainer.EMPH)
                    ]
                ),
                OpenerArgs(0, 0, '_')
            ),
            TestCase(
                'braced emphasis open',
                Args(
                    text='{_emph_}',
                    pos=1,
                    endpos=7,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                ),
                OpenerArgs(0, 0, '{_', InlineLeaf.OPEN_MARKER)
            ),
            TestCase(
                'braced emphasis close',
                Args(
                    text='{_emph_}',
                    pos=6,
                    endpos=7,
                ),
                Expected(
                    pos=8,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.EMPH),
                        Event.exit(Range(6, 7), InlineContainer.EMPH)
                    ]
                ),
                OpenerArgs(0, 1, '{_')
            ),
        ]

        for name, args, expected, state_arg in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                if isinstance(state_arg, OpenerArgs):
                    populate_between_state(state, state_arg)
                matcher = EmphMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_strong(self):
        cases = [
            TestCase(
                'strong open',
                Args(
                    text='*a*',
                    pos=0,
                    endpos=2,
                ),
                Expected(
                    pos=1,
                    events=[
                        Event.str(0, 0)
                    ]
                ),
                None,
            ),
            TestCase(
                'strong close',
                Args(
                    text='*a*',
                    pos=2,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.STRONG),
                        Event.exit(Range(2, 2), InlineContainer.STRONG)
                    ]
                ),
                OpenerArgs(0, 0, '*')
            ),
            TestCase(
                'braced strong open',
                Args(
                    text='{*a*}',
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                ),
                OpenerArgs(0, 0, '{*', InlineLeaf.OPEN_MARKER)
            ),
            TestCase(
                'braced strong close',
                Args(
                    text='{*a*}',
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.STRONG),
                        Event.exit(Range(3, 4), InlineContainer.STRONG)
                    ]
                ),
                OpenerArgs(0, 1, '{*')
            ),
        ]

        for name, args, expected, state_arg in cases:
            with self.subTest(f'{name}: {args.text}'):

                state = InlineState(InputText(args.text), Options())
                if isinstance(state_arg, OpenerArgs):
                    populate_between_state(state, state_arg)

                matcher = StrongMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)

                self.assertEqual(state.events, expected.events)

    def test_insert(self):
        cases = [
            TestCase(
                'insert open',
                Args(
                    text='{+a+}',
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                ),
                OpenerArgs(0, 0, '{+', InlineLeaf.OPEN_MARKER)
            ),
            TestCase(
                'insert close',
                Args(
                    text='{+a+}',
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.INSERT),
                        Event.exit(Range(3, 4), InlineContainer.INSERT)
                    ]
                ),
                OpenerArgs(0, 1, '{+')
            ),
        ]

        for name, args, expected, state_arg in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                if isinstance(state_arg, OpenerArgs):
                    populate_between_state(state, state_arg)
                matcher = InsertMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)
    
    def test_hyphen(self):
        cases = [
            TestCase(
                'delete open',
                Args(
                    text='{-a-}',
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                ),
                OpenerArgs(0, 0, '{-', InlineLeaf.OPEN_MARKER)
            ),
            TestCase(
                'delete close',
                Args(
                    text='{-a-}',
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.DELETE),
                        Event.exit(Range(3, 4), InlineContainer.DELETE)
                    ]
                ),
                OpenerArgs(0, 1, '{-')
            ),
            TestCase(
                'dash brace',
                Args(
                    text='-}',
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
                    text='---',
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
                    text='--',
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
                    text='-----',
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

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                if isinstance(state_args, OpenerArgs):
                    populate_between_state(state, state_args)
                matcher = HyphenMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_mark(self):
        cases = [
            TestCase(
                'mark open',
                Args(
                    text='{=a=}',
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.str(0, 1)
                    ]
                ),
                OpenerArgs(0, 0, '{=', InlineLeaf.OPEN_MARKER)
            ),
            TestCase(
                'mark close',
                Args(
                    text='{=a=}',
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.MARK),
                        Event.exit(Range(3, 4), InlineContainer.MARK)
                    ]
                ),
                OpenerArgs(0, 1, '{=')
            ),
        ]

        for name, args, expected, state_args in cases:
                with self.subTest(f'{name}: {args.text}'):
                    state = InlineState(InputText(args.text), Options())
                    if isinstance(state_args, OpenerArgs):
                        populate_between_state(state, state_args)
                matcher = MarkMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_single_quote(self):
        cases = [
            TestCase(
                'left single quote',
                Args(
                    text="'a'",
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
                    text="'a'",
                    pos=2,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.SINGLE_QUOTED),
                        Event.exit(Range(2, 2), InlineContainer.SINGLE_QUOTED)
                    ]
                ),
                OpenerArgs(0, 0, "'", InlineLeaf.RIGHT_SINGLE_QUOTE)
            ),
            TestCase(
                'braced left single quote',
                Args(
                    text="{'a'}",
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.leaf(Range(0, 1), InlineLeaf.LEFT_SINGLE_QUOTE)
                    ]
                ),
                OpenerArgs(0, 0, '{', InlineLeaf.OPEN_MARKER)
            ),
            TestCase(
                'braced right single quote',
                Args(
                    text="{'a'}",
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.SINGLE_QUOTED),
                        Event.exit(Range(3, 4), InlineContainer.SINGLE_QUOTED)
                    ]
                ),
                OpenerArgs(0, 1, "{'")
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                if isinstance(state_args, OpenerArgs):
                    populate_between_state(state, state_args)
                matcher = SingleQuoteMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_double_quote(self):
        cases = [
            TestCase(
                'left double quote',
                Args(
                    text='"a"',
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
                    text='"a"',
                    pos=2,
                    endpos=2,
                ),
                Expected(
                    pos=3,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.DOUBLE_QUOTED),
                        Event.exit(Range(2, 2), InlineContainer.DOUBLE_QUOTED)
                    ]
                ),
                OpenerArgs(0, 0, '"', InlineLeaf.LEFT_DOUBLE_QUOTE)
            ),
            TestCase(
                'braced left double quote',
                Args(
                    text='{"a"}',
                    pos=1,
                    endpos=4,
                ),
                Expected(
                    pos=2,
                    events=[
                        Event.leaf(Range(0, 0), InlineLeaf.OPEN_MARKER),
                        Event.leaf(Range(0, 1), InlineLeaf.LEFT_DOUBLE_QUOTE)
                    ]
                ),
                OpenerArgs(0, 0, '{', InlineLeaf.OPEN_MARKER)
            ),
            TestCase(
                'braced right double quote',
                Args(
                    text='{"a"}',
                    pos=3,
                    endpos=4,
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.DOUBLE_QUOTED),
                        Event.exit(Range(3, 4), InlineContainer.DOUBLE_QUOTED)
                    ]
                ),
                OpenerArgs(0, 1, '{"')
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                if isinstance(state_args, OpenerArgs):
                    populate_between_state(state, state_args)
                matcher = DoubleQuoteMatcher()
                actual_pos = matcher(state, args.pos, args.endpos)
                self.assertEqual(actual_pos, expected.pos)
                self.assertEqual(state.events, expected.events)


class BareArgs(NamedTuple):
    text: str
    pos: int
    can_open: bool

class BraceArgs(NamedTuple):
    text: str
    pos: int
    endpos: int
    last_event: Event | None

class TestBetweenMatcher(unittest.TestCase):
    def test_bare_context(self):
        cases = [
            (
                'bare open',
                BareArgs(
                    text='*bold*',
                    pos=0,
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
                    text='*bold*',
                    pos=5,
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
                    text='a*b',
                    pos=1,
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
            with self.subTest(f'{name}: {args.text}'):
                cursor = InputText(args.text)
                actual = determine_bare_context(
                    cursor,
                    args.pos,
                    args.can_open
                )
                self.assertEqual(actual, expected)

    def test_brace_context(self):
        cases = [
            (
                'brace open',
                BraceArgs(
                    text='{*bold*}',
                    pos=1,
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
                    text='{*bold*}',
                    pos=6,
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
            with self.subTest(f'{name}: {args.text}'):
                cursor = InputText(args.text)
                actual = determine_brace_context(
                    cursor,
                    args.pos,
                    args.endpos,
                    args.last_event
                )
                self.assertEqual(actual, expected)

    def test_handle_opener(self):
        cases = [
            TestCase(
                'handle opener',
                Args(
                    text='*bold*',
                    pos=0,
                    endpos=5,
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
                None,
            ),
            TestCase(
                'handle brace opener',
                Args(
                    text='{*bold*}',
                    pos=1,
                    endpos=7,
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
                OpenerArgs(0, 0, '{*', InlineLeaf.OPEN_MARKER)
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                state = InlineState(InputText(args.text), Options())
                if isinstance(state_args, OpenerArgs):
                    populate_between_state(state, state_args)

                matcher = StrongMatcher()

                assert args.ctx is not None
                actual = matcher._handle_opener(
                    state,
                    args.pos,
                    args.ctx,
                )
                self.assertEqual(actual, expected.pos)
                self.assertEqual(state.events, expected.events)

    def test_handle_closer(self):
        cases = [
            (
                'handle closer',
                Args(
                    text='*bold*',
                    pos=5,
                    endpos=5,
                    ctx=MatchContext(
                        delimiter_cap=DelimiterCap.CAN_CLOSE,
                        token_start=5,
                        token_end=5,
                        marker_style=MarkerStyle.NONE
                    ),
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.enter(Range(0, 0), InlineContainer.STRONG),
                        Event.exit(Range(5, 5), InlineContainer.STRONG)
                    ]
                ),
                OpenerArgs(0, 0, '*')
            ),
            (
                'handle brace closer',
                Args(
                    text='{*bold*}',
                    pos=6,
                    endpos=7,
                    ctx=MatchContext(
                        delimiter_cap=DelimiterCap.CAN_CLOSE,
                        token_start=6,
                        token_end=7,
                        marker_style=MarkerStyle.CLOSE,
                    ),
                ),
                Expected(
                    pos=8,
                    events=[
                        Event.enter(Range(0, 1), InlineContainer.STRONG),
                        Event.exit(Range(6, 7), InlineContainer.STRONG)
                    ],
                ),
                OpenerArgs(0, 1, '{*')
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                
                state = InlineState(InputText(args.text), Options())
                if state_args:
                    populate_between_state(state, state_args)
                
                matcher = StrongMatcher()

                assert args.ctx is not None
                actual = matcher._handle_closer(
                    state=state,
                    ctx=args.ctx,
                    pos=args.pos,
                    opener=state.get_openers(state_args.token_name)[-1]
                )
                self.assertEqual(actual, expected.pos)
                self.assertEqual(state.events, expected.events)


class TestInlineParser(unittest.TestCase):
    def test_feed_attribute(self):
        attr = '{#ident .dark key=value key2="val2 val3"}'
        cases = [
            (
                'inline attributes',
                Args(
                    text=attr,
                    pos=0,
                    endpos=len(attr) - 1
                ),
                Expected(
                    pos=len(attr),
                    events=[
                        Event.enter(Range(0, 0), BlockContainer.ATTRIBUTES),
                        Event.attr(Range(1, 1), AttrKind.ID_START),
                        Event.attr(Range(2, 6), AttrKind.ID),
                        Event.attr(Range(7, 7), AttrKind.SPACE),
                        Event.attr(Range(8, 8), AttrKind.CLASS_START),
                        Event.attr(Range(9, 12), AttrKind.CLASS),
                        Event.attr(Range(13, 13), AttrKind.SPACE),
                        Event.attr(Range(14, 16), AttrKind.KEY),
                        Event.attr(Range(17, 17), AttrKind.EQUAL_MARKER),
                        Event.attr(Range(18, 22), AttrKind.VALUE),
                        Event.attr(Range(23, 23), AttrKind.SPACE),
                        Event.attr(Range(24, 27), AttrKind.KEY),
                        Event.attr(Range(28, 28), AttrKind.EQUAL_MARKER),
                        Event.attr(Range(29, 29), AttrKind.QUOTE_MARKER),
                        Event.attr(Range(30, 38), AttrKind.VALUE),
                        Event.attr(Range(39, 39), AttrKind.QUOTE_MARKER),
                        Event.exit(Range(40, 40), BlockContainer.ATTRIBUTES),
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.text}'):
                parser = InlineParser(
                    cursor=InputText(args.text),
                    options=Options()
                )
                actual = parser._feed_attribute(args.pos, args.endpos)
                self.assertEqual(actual, expected.pos)
                self.assertEqual(parser.state.events, expected.events)

    def test_feed_str_before_special(self):
        strong = 'foo *bar*'
        no_special = 'foo bar'
        cases = [
            (
                'str before *',
                Args(
                    text=strong,
                    pos=0,
                    endpos=len(strong) - 1
                ),
                Expected(
                    pos=4,
                    events=[
                        Event.str(0, 3)
                    ]
                )
            ),
            (
                'no special',
                Args(
                    text=no_special,
                    pos=0,
                    endpos=len(no_special) - 1
                ),
                Expected(
                    pos=7,
                    events=[
                        Event.str(0, 6)
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.text}'):
                parser = InlineParser(
                    cursor=InputText(args.text),
                    options=Options()
                )
                actual = parser._feed_str_before_special(args.pos, args.endpos)
                self.assertEqual(actual, expected.pos)
                self.assertEqual(parser.state.events, expected.events)

    def test_feed_newline(self):
        crlf = 'foo\r\n'
        linefeed = 'foo\n'

        cases = [
            (
                'cr and lf',
                Args(
                    text=crlf,
                    pos=3,
                    endpos=len(crlf) - 1
                ),
                Expected(
                    pos=5,
                    events=[
                        Event.leaf(Range(3, 4), InlineLeaf.SOFT_BREAK)
                    ]
                )
            ),
            (
                'linefeed',
                Args(
                    text=linefeed,
                    pos=3,
                    endpos=len(linefeed) - 1
                ),
                Expected(
                    pos=4,
                    events=[
                        Event.leaf(Range(3, 3), InlineLeaf.SOFT_BREAK)
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.text}'):
                parser = InlineParser(
                    cursor=InputText(args.text),
                    options=Options()
                )
                actual = parser._feed_newline(args.pos, args.endpos)
                self.assertEqual(actual, expected.pos)
                self.assertEqual(parser.state.events, expected.events)

    def test_feed_verbatim(self):

        example = '`foo``bar`{=html}'
        math = '$`x^2`'

        cases = [
            (
                'unequal backtick',
                Args(
                    text=example,
                    pos=4,
                    endpos=len(example) - 1
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.str(4, 5)
                    ]
                ),
                VerbArgs(len=1)
            ),
            (
                'raw inline',
                Args(
                    text=example,
                    pos=9,
                    endpos=len(example) - 1
                ),
                Expected(
                    pos=17,
                    events=[
                        Event.exit(Range(9, 9), VerbatimKind.VERBATIM),
                        Event.leaf(Range(10, 16), InlineLeaf.RAW_FORMAT)
                    ]
                ),
                VerbArgs(len=1)
            ),
            (
                'math',
                Args(
                    text=math,
                    pos=5,
                    endpos=len(math) - 1
                ),
                Expected(
                    pos=6,
                    events=[
                        Event.exit(Range(5, 5), VerbatimKind.INLINE_MATH),
                    ]
                ),
                VerbArgs(len=1, typ=VerbatimKind.INLINE_MATH)
            ),
        ]

        for name, args, expected, state_args in cases:
            with self.subTest(f'{name}: {args.text}'):
                parser = InlineParser(InputText(args.text), Options())
                populate_verb_state(parser.state, state_args)
                actual = parser._feed_closing_verbatim(args.pos, args.endpos)
                self.assertEqual(actual, expected.pos)
                self.assertEqual(parser.state.events, expected.events)

    def test_feed_matcher(self):
        example = 'foo.'

        cases = [
            (
                'matcher fallback',
                Args(
                    text=example,
                    pos=3,
                    endpos=len(example) - 1
                ),
                Expected(
                    pos=4,
                    events=[
                        Event.str(3, 3)
                    ]
                )
            )
        ]

        for name, args, expected in cases:
            with self.subTest(f'{name}: {args.text}'):
                parser = InlineParser(
                    cursor=InputText(args.text),
                    options=Options()
                )
                actual = parser._feed_matcher(args.pos, args.endpos)
                self.assertEqual(actual, expected.pos)
                self.assertEqual(parser.state.events, expected.events)

    def test_feed(self):
        cases = [
            (
                'simple text'
            )
        ]

if __name__ == '__main__':
    unittest.main()