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

    
    def feed(self, startpos: int, endpos: int):
        # Position firstpos and endpos as far as possible.
        self._update_boudary(startpos, endpos)

        pos = startpos
        while pos <= endpos:
            if self.state.in_attribute:
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
        """
        Parse attributes

        Workfllow:
        LeftBraceMatcher -> Init AttributeParser -> Keep pos in place
        -> next loop in feed -> _feed_attribute()

        Args:
            pos (int): start position of {
            endpos (int): end position of line
        """
        sp = pos

        attribute_parser = AttributeParser(self.state.cursor)

        result = attribute_parser.feed(sp, endpos)

        match result.status:
            case AttrFlowControl.DONE:
                
                self.state.push_event(
                    Event.enter( # The opening {
                        kind=BlockContainer.ATTRIBUTES,
                        span=Range(sp, sp)
                    )
                )

                # Transfer attribute events.
                self.state.extend_events(attribute_parser.events)
                self.state.push_event(
                    Event.exit(
                        kind=BlockContainer.ATTRIBUTES,
                        span=Range(result.position, result.position)
                    )
                )

                # restore state to prior to adding attribute parser
                self.state.reset_attribute_state()
                return result.position + 1
            case AttrFlowControl.FAIL:
                # If attribute parsing failed, turn pending Span to str.
                # And then add { as plain text event. Then move cursor forward.
                self.state.demote_span_to_str()
                self.state.push_event(
                    Event.str(sp, sp)
                )

                self.state.reset_attribute_state()
                # No self.reparse_attributes() here
                return sp+1
    
    def _feed_str_before_special(self, pos: int, endpos: int) -> int:
        """
        Find any special characters in a line, and take anything
        beofore the found char as plain text.
        If not spcial char is found, the rest of line is taken
        as plain text.

        Example: [^foo]
        pos -> 1, ^
        endpos -> 5, ]
        next_sepcial -> 1
        newpos == pos
        No event added
        return 1
        """
        next_special = self.cursor.find_special(pos, endpos)

        newpos = endpos + 1 if next_special is None else next_special

        if newpos > pos:
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, newpos-1),
                    kind=InlineLeaf.STR
                )
            )

        return newpos

        
    def _feed_newline(self, pos: int, endpos: int) -> Optional[int]:

        if self.cursor.is_cr_or_lf(pos):
            if self.cursor.is_crlf(pos):
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

        count = self.cursor.count_char('`', pos)

        # In verbatim string, the special char is not backtick.
        if count == 0:
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, pos),
                    kind=InlineLeaf.STR
                )
            )
            return pos + 1

        # backtick found
        endchar = pos + count - 1

        # Opening and closing delimiters should be equal.
        if count != self.verbatim_len:
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, endchar),
                    kind=InlineLeaf.STR
                )
            )

        # Check for raw attribute
        endchar = pos + count - 1
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