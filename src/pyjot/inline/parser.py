from typing import Dict, Iterator, Optional

from ..input import InputText
from ..options import Options
from ..event import (
    Event,
    InlineLeaf,
    BlockContainer,
    InlineLeaf,
    VerbatimKind,
)
from ..common import Range
from ..attributes import (
    AttributeParser,
    AttrFlowControl
)

from .state import InlineState
from .matcher import Matcher
from .backtick import BacktickMatcher
from .backslash import BackslashMatcher
from .lessthan import LessthanMatcher
from .between import (
    SubscriptMatcher,
    SuperscriptMatcher,
    EmphMatcher,
    StrongMatcher,
    InsertMatcher,
    MarkMatcher,
    SingleQuoteMatcher,
    DoubleQuoteMatcher,
)
from .brace_left import LeftBraceMatcher
from .colon import ColonMatcher
from .period import PeriodMatcher
from .bracket_left import LeftBracketMatcher
from .bracket_right import RightBracketMatcher
from .paren_left import LeftParenMatcher
from .paren_right import RightParenMatcher
from .hyphen import HyphenMatcher

MATCHERS: Dict[str, Matcher] = {
    '`': BacktickMatcher(),
    '\\': BackslashMatcher(),
    '<': LessthanMatcher(),
    # H~2~O
    '~': SubscriptMatcher(),
    '^': SuperscriptMatcher(),
    '_': EmphMatcher(),
    '*': StrongMatcher(),
    '+': InsertMatcher(),
    '=': MarkMatcher(),
    "'": SingleQuoteMatcher(),
    '"': DoubleQuoteMatcher(),
    '{': LeftBraceMatcher(),
    ':': ColonMatcher(),
    '.': PeriodMatcher(),
    '[': LeftBracketMatcher(),
    ']': RightBracketMatcher(),
    '(': LeftParenMatcher(),
    ')': RightParenMatcher(),
    '-': HyphenMatcher(),
}

class InlineParser:
    def __init__(self, cursor: InputText, options: Options):
        self.options = options
        self.cursor = cursor
        self.state = InlineState(cursor, options)

        self.firstpos = -1 # position of first slice
        self.lastpos = 0 # position of last slice
        self.matchers = MATCHERS

    @property
    def in_verbatim(self) -> bool:
        return self.state.verbatim_len > 0

    def _single_char(self, pos: int) -> int:
        self.state.events.append(
            Event.leaf(
                span=Range(pos, pos),
                kind=InlineLeaf.STR
            )
        )
        return pos + 1

    def iter_merged_events(self) -> Iterator[Event]:
    
        last_str: Optional[Event] = None # str cache.

        for current in self.state.get_matches():
            # Current event is not str, clear cache and yield current event.
            if current.kind != InlineLeaf.STR:
                # State change, flush cache.
                if last_str:
                    yield last_str
                    last_str = None
                yield current
                continue

            # Current event is str and cache is empty, cache it.
            if not last_str:
                last_str = current
                continue

            # Current event is str, and it is adjacent to last str, extend it.
            if last_str.span.end + 1 == current.span.start:
                # Creat a new Range to avoid messing with the original Range.
                last_str.span = Range(
                    start=last_str.span.start,
                    end=current.span.end
                )
                continue
            
            # Current event is str, and it is not adjacent to last str, 
            # yield it and cache the current event.
            last_str = current

        if last_str:
            yield last_str

    def _update_boudary(self, startpos: int, endpos: int):
    
        if self.firstpos == -1 or startpos < self.firstpos:
            self.firstpos = startpos

        if self.lastpos == 0 or endpos > self.lastpos:
            self.lastpos = endpos

    def init_attribute_parser(self, pos: int):
        """Create attribute parser
        
        When a `{` if encountered, and it is not followed by
        inline markup like *, -, etc., it is taken as starting
        attributes.
        """
        self.attribute_parser = AttributeParser(self.cursor)
        self.attribute_start = pos
        self.attribute_spans = []

    def _reset_attribute_state(self):
        self.attribute_parser = None
        self.attribute_start = None
        self.attribute_spans = None
        self.pending_span = None

    
    def feed(self, startpos: int, endpos: int):
        # Position firstpos and endpos as far as possible.
        self._update_boudary(startpos, endpos)

        pos = startpos
        while pos <= endpos:
            if self.attribute_parser is not None:
                pos = self._feed_attribute(pos, endpos)
                continue
            else:
                pos = self._feed_str_before_special(pos, endpos)
                if pos > endpos: # gobbled whole line
                    break 

                # if we get here, then pos points to some special char,
                # i.e. we have something interesting at pos
                newpos = self._feed_newline(pos, endpos)
                if newpos is not None:
                    pos = newpos
                    continue

                newpos = self._feed_verbatim(pos, endpos)
                if newpos is not None:
                    pos = newpos
                    continue

                pos = self._feed_matcher(pos, endpos)

    
    def _feed_attribute(self, pos: int, endpos: int) -> int:
        sp = pos
        next_special = self.cursor.find_special(pos, endpos)
        ep2 = endpos if next_special is None else next_special

        assert self.attribute_parser is not None

        result = self.attribute_parser.feed(sp, ep2)
        ep = result.position

        match result.status:
            case AttrFlowControl.DONE:
                attribute_start = self.attribute_start
                
                if attribute_start is not None:
                    self.state.events.append(
                        Event.enter( # The opening {
                            kind=BlockContainer.ATTRIBUTES,
                            span=Range(attribute_start, attribute_start)
                        )
                    )

                # Transfer attribute events.
                self.state.events.extend(self.attribute_parser.events)
                self.state.events.append(
                    Event.exit(
                        kind=BlockContainer.ATTRIBUTES,
                        span=Range(ep, ep)
                    )
                )

                # restore state to prior to adding attribute parser
                self._reset_attribute_state()
                return ep + 1
            case AttrFlowControl.FAIL:
                # self.reparse_attributes()
                return sp
            case AttrFlowControl.CONTINUE:
                if self.attribute_spans is None:
                    self.attribute_spans = []
                self.attribute_spans.append(
                    Range( # the whole range of `{...}`
                        start=sp,
                        end=ep,
                    )
                )
                return ep + 1
    
    def _feed_str_before_special(self, pos: int, endpos: int) -> int:
        """
        Find any special characters in a line, and take anything
        beofore the found char as plain text.
        If not spcial char is found, the rest of line is taken
        as plain text.
        """
        next_special = self.cursor.find_special(pos, endpos)

        newpos = endpos + 1 if next_special is None else next_special

        if newpos > pos:
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, endpos),
                    kind=InlineLeaf.STR
                )
            )

        return newpos

        
    def _feed_newline(self, pos: int, endpos: int) -> Optional[int]:
        ch = self.cursor.char_at(pos)
        if ch is None:
            raise Exception(f'char at {pos} is undefined')

        if ch == '\r' or ch == '\n':
            if ch == '\r' and self.cursor.char_at(pos+1) == '\n':
                self.state.events.append(
                    Event.leaf(
                        span=Range(pos, pos+1),
                        kind=InlineLeaf.SOFT_BREAK,
                    )
                )
                return pos + 2
            
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, pos),
                    kind=InlineLeaf.SOFT_BREAK,
                )
            )
            return pos + 1

        return None
                

    def _feed_verbatim(self, pos: int, endpos) -> Optional[int]:
        if self.verbatim_len <= 0: # not in verbatim mode
            return None

        ch = self.cursor.char_at(pos)
        if ch is None:
            raise Exception(f'char at {pos} is undefined')

        if ch != '`': # check verbatim closing mark
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, pos),
                    kind=InlineLeaf.STR
                )
            )
            return pos + 1
        
        m = self.cursor.find_backtick_at_least_one(pos, endpos)
        if not m: # why this could happen if you are searching from the backtick?
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, endpos),
                    kind=InlineLeaf.STR
                )
            )
            return endpos + 1

        # Opening and closing delimiters should be equal.
        if m.end - pos + 1 != self.verbatim_len:
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, m.end),
                    kind=InlineLeaf.STR
                )
            )

        # Check for raw attribute
        endchar = m.end
        m2 = self.cursor.find_raw_attribute(endchar+1, endpos)
        if m2 and self.verbatim_type == VerbatimKind.VERBATIM: # raw
            self.state.events.append(
                Event.exit(
                    kind=self.verbatim_type,
                    span=Range(pos, endchar) # the backtick
                )
            )
            self.state.events.append(
                Event.leaf(
                    span=Range(m2.start, m2.end),
                    kind=InlineLeaf.RAW_FORMAT,
                )
            )
            pos = m2.end + 1
        else:
            self.state.events.append(
                Event.exit(
                    kind=self.verbatim_type,
                    span=Range(pos, endchar)
                )
            )
            pos = endchar + 1

        self.verbatim_len = 0
        self.verbatim_type = VerbatimKind.VERBATIM
        return pos

    def _feed_matcher(self, pos: int, endpos: int) -> int:
        ch = self.cursor.char_at(pos)
        if ch is None:
            raise Exception(f'char at {pos} is undefined')

        if ch in self.matchers:
            matcher = self.matchers[ch]
            res = matcher(self.state, pos, endpos)
            if res is not None:
                return res

            pos = self._single_char(pos)
            return pos

        return self._single_char(pos)