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
    BlockContainer,
    Action
)
from djot.common import Range
from djot.inline.state import InlineState, OpenerKind
from djot.input import InputText
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

def event_opener_marker(startpos: int, endpos: int) -> Event:
    return Event.leaf(
        Range(startpos, endpos),
        InlineLeaf.OPEN_MARKER
    )

def event_attributes(startpos: int, endpos: int, open: bool = True) -> Event:
    return Event(
        span=Range(startpos, endpos),
        kind=BlockContainer.ATTRIBUTES,
        action=Action.ENTER if open else Action.EXIT,
    )

def event_span(startpos: int, endpos: int, open: bool = True) -> Event:
    return Event(
        span=Range(startpos, endpos),
        kind=InlineContainer.SPAN,
        action=Action.ENTER if open else Action.EXIT,
    )

def attr_id_marker(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.ID_MARKER
    )

def attr_id(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.ID
    )

def attr_space(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.SPACE
    )

def attr_class_marker(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.CLASS_MARKER
    )

def attr_class(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.CLASS
    )

def attr_key(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.KEY
    )

def attr_equal_marker(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.EQUAL_MARKER
    )

def attr_quote_marker(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.QUOTE_MARKER
    )

def attr_value(startpos: int, endpos: int) -> Event:
    return Event.attr(
        Range(startpos, endpos),
        AttrKind.VALUE
    )

def event_link_text(startpos: int, endpos: int, open: bool = True) -> Event:
    return Event(
        span=Range(startpos, endpos),
        kind=InlineContainer.LINK_TEXT,
        action=Action.ENTER if open else Action.EXIT,
    )

def event_dest(startpos: int, endpos: int, open: bool = True) -> Event:
    return Event(
        span=Range(startpos, endpos),
        kind=InlineContainer.DESTINATION,
        action=Action.ENTER if open else Action.EXIT,
    )

def event_reference(starpos: int, endpos: int, open: bool = True) -> Event:
    return Event(
        span=Range(starpos, endpos),
        kind=InlineContainer.REFERENCE,
        action=Action.ENTER if open else Action.EXIT,
    )

def event_image_marker(startpos: int, endpos: int) -> Event:
    return Event.leaf(
        span=Range(startpos, endpos),
        kind=InlineLeaf.IMAGE_MARKER,
    )

def event_image_text(startpos: int, endpos: int, open: bool = True) -> Event:
    return Event(
        span=Range(startpos, endpos),
        kind=InlineContainer.IMAGE_TEXT,
        action=Action.ENTER if open else Action.EXIT,
    )

class TestInlineParser(unittest.TestCase):

    def test_basic_parsing(self):
        text = 'hello there'

        parser = InlineParser(
            cursor=InputText(text),
        )

        parser.feed(0, 6)
        parser.feed(8, 10)

        expected = [
            Event.str(0, 6),
            Event.str(8, 10)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_verbatim(self):
        text = "x ``` hello ``there ``` x"
        parser = InlineParser(
            cursor=InputText(text),
        )

        parser.feed(0, 24)

        expected = [
            Event.str(0, 1),
            Event.enter(Range(2, 4), VerbatimKind.VERBATIM),
            Event.str(5, 11),
            Event.str(12, 13),
            Event.str(14, 19),
            Event.exit(Range(20, 22), VerbatimKind.VERBATIM),
            Event.str(23, 24)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_parse_escaped(self):
        text = '\\"\\*\\ \\a \\\n'
        parser = InlineParser(
            cursor=InputText(text),
            
        )
        parser.feed(0, 10)

        expected = [
            Event.escape(0, 0),
            Event.str(1, 1),
            Event.escape(2, 2),
            Event.str(3, 3),
            Event.escape(4, 4),
            Event.nbsp(5, 5),
            Event.str(6, 6),
            Event.str(7, 7),
            Event.escape(9, 9),
            Event.hardbreak(10, 10)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_parse_autolinks(self):
        parser = InlineParser(
            cursor=InputText('<http://example.com?foo=bar&baz=&amp;x2>'),
            
        )

        parser.feed(0, 39)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.URL),
            Event.str(1, 38),
            Event.exit(Range(39, 39), InlineContainer.URL),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_parse_email_autolinks(self):
            parser = InlineParser(
                cursor=InputText('<me@example.com>'),
                
            )
    
            parser.feed(0, 15)
    
            expected = [
                Event.enter(Range(0, 0), InlineContainer.EMAIL),
                Event.str(1, 14),
                Event.exit(Range(15, 15), InlineContainer.EMAIL),
            ]
    
            self.assertEqual(parser.state.get_matches(), expected)

    def test_super_subscript(self):
        parser = InlineParser(
            cursor=InputText('H~2~O e=mc^2^ test{^two words^}'),
            
        )

        parser.feed(0, 30)

        expected = [
             Event.str(0, 0),
             Event.enter(Range(1, 1), InlineContainer.SUBSCRIPT),
             Event.str(2, 2),
             Event.exit(Range(3, 3), InlineContainer.SUBSCRIPT),
             Event.str(4, 6),
             Event.str(7, 7),
             Event.str(8, 9),
             Event.enter(Range(10, 10), InlineContainer.SUPERSCRIPT),
             Event.str(11, 11),
             Event.exit(Range(12, 12), InlineContainer.SUPERSCRIPT),
             Event.str(13, 17),
             Event.leaf(Range(18, 18), InlineLeaf.OPEN_MARKER),
             Event.enter(Range(18, 19), InlineContainer.SUPERSCRIPT),
             Event.str(20, 28),
             Event.exit(Range(29, 30), InlineContainer.SUPERSCRIPT),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_emphasis(self):
        parser = InlineParser(
            cursor=InputText('_hello *there*_ world'),
            
        )

        parser.feed(0, 20)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.EMPH),
            Event.str(1, 6),
            Event.enter(Range(7, 7), InlineContainer.STRONG),
            Event.str(8, 12),
            Event.exit(Range(13, 13), InlineContainer.STRONG),
            Event.exit(Range(14, 14), InlineContainer.EMPH),
            Event.str(15, 20)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_mark(self):
        parser = InlineParser(
            cursor=InputText('{=hello=}'),
            
        )
        parser.feed(0, 8)
        expected = [
            event_opener_marker(0, 0),
            Event.enter(Range(0, 1), InlineContainer.MARK),
            Event.str(2, 6),
            Event.exit(Range(7, 8), InlineContainer.MARK)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_inserted(self):
        parser = InlineParser(
            cursor=InputText('{+hello+}'),
            
        )
        parser.feed(0, 8)
        expected = [
            event_opener_marker(0, 0),
            Event.enter(Range(0, 1), InlineContainer.INSERT),
            Event.str(2, 6),
            Event.exit(Range(7, 8), InlineContainer.INSERT)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_quoted(self):
        parser = InlineParser(
            cursor=InputText('"dog\'s breakfast"'),
            
        )

        parser.feed(0, 16)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.DOUBLE_QUOTED),
            Event.str(1, 3),
            Event.right_single_quote(4, 4),
            Event.str(5, 15),
            Event.exit(Range(16, 16), InlineContainer.DOUBLE_QUOTED),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_parse_attributes(self):
        parser = InlineParser(
            cursor=InputText('{#foo .bar baz="bim"}'),
            
        )

        parser.feed(0, 20)

        expected = [
            event_attributes(0, 0),
            Event.attr(Range(1, 1), AttrKind.ID_MARKER),
            Event.attr(Range(2, 4), AttrKind.ID),
            Event.attr(Range(5, 5), AttrKind.SPACE),
            Event.attr(Range(6, 6), AttrKind.CLASS_MARKER),
            Event.attr(Range(7, 9), AttrKind.CLASS),
            Event.attr(Range(10, 10), AttrKind.SPACE),
            Event.attr(Range(11, 13), AttrKind.KEY),
            Event.attr(Range(14, 14), AttrKind.EQUAL_MARKER),
            Event.attr(Range(15, 15), AttrKind.QUOTE_MARKER),
            Event.attr(Range(16, 18), AttrKind.VALUE),
            Event.attr(Range(19, 19), AttrKind.QUOTE_MARKER),
            event_attributes(20, 20, False),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_spans(self):
        parser = InlineParser(
            cursor=InputText('[hi]{#foo .bar baz="bim"}'),
            
        )

        parser.feed(0, 24)

        expected = [
            event_span(0, 0),
            Event.str(1, 2),
            event_span(3, 3, False),
            event_attributes(4, 4),
            attr_id_marker(5, 5),
            attr_id(6, 8),
            attr_space(9, 9),
            attr_class_marker(10, 10),
            attr_class(11, 13),
            attr_space(14, 14),
            attr_key(15, 17),
            attr_equal_marker(18, 18),
            attr_quote_marker(19, 19),
            attr_value(20, 22),
            attr_quote_marker(23, 23),
            event_attributes(24, 24, False),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_inline_links(self):
        parser = InlineParser(
            cursor=InputText('[foobar](url)'),
            
        )

        parser.feed(0, 12)

        expected = [
            event_link_text(0, 0),
            Event.str(1, 6),
            event_link_text(7, 7, False),
            event_dest(8, 8),
            Event.str(9, 11),
            event_dest(12, 12, False)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_refrence_links(self):
        parser = InlineParser(
            cursor=InputText('[foobar][1]'),
            
        )

        parser.feed(0, 10)

        expected = [
            event_link_text(0, 0),
            Event.str(1, 6),
            event_link_text(7, 7, False),
            event_reference(8, 8),
            Event.str(9, 9),
            event_reference(10, 10, False),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_inline_image(self):
        parser = InlineParser(
            cursor=InputText('![foobar](url)'),
            
        )
        parser.feed(0, 13)
        expected = [
            event_image_marker(0, 0),
            event_image_text(1, 1),
            Event.str(2, 7),
            event_image_text(8, 8, False),
            event_dest(9, 9),
            Event.str(10, 12),
            event_dest(13, 13, False)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_symbs(self):
        parser = InlineParser(
            cursor=InputText(':+1:'),
            
        )

        parser.feed(0, 3)

        expected = [
            Event.leaf(Range(0, 3), InlineLeaf.SYMBOL),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_ellipses(self):
        parser = InlineParser(
            cursor=InputText('...'),
            
        )

        parser.feed(0, 2)

        expected = [
            Event.leaf(Range(0, 2), InlineLeaf.ELLIPSES),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_dashes(self):
        parser = InlineParser(
            cursor=InputText('a---b--c'),
            
        )
        parser.feed(0, 7)

        expected = [
            Event.str(0, 0),
            Event.leaf(Range(1, 3), InlineLeaf.EM_DASH),
            Event.str(4, 4),
            Event.leaf(Range(5, 6), InlineLeaf.EN_DASH),
            Event.str(7, 7),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_note_reference(self):
        parser = InlineParser(
            cursor=InputText('[^ref]'),
            
        )

        parser.feed(0, 5)

        expected = [
            Event.leaf(Range(0, 5), InlineLeaf.FOOTNOTE_REF)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

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
    state = InlineState(InputText(text))
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

    state = InlineState(InputText(text))

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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state=InlineState(InputText(args.text))
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
                state=InlineState(InputText(args.text))
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
                state=InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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

                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                state = InlineState(InputText(args.text))
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
                
                state = InlineState(InputText(args.text))
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




if __name__ == '__main__':
    unittest.main()