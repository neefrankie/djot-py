from typing import Dict, Iterator, NamedTuple, Optional

from djot.cursor import (
    Cursor,
    LineContext,
)
from djot.event import (
    Event,
    VerbatimKind,
    InlineContainer,
    InlineLeaf,
    InlineLeaf,
)
from djot.common import Range
from djot.attributes import (
    AttributeParser,
    AttrStatus,
)
from djot.logger import logger

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

# TODO: is it possible to handle table row parsing by adding a '|'?
# When block parser deteced a table row, it put inline parser into table mode.
# When in table mode, inline parser delegate to PipeMatcher when it sees a '|'.
# In verbatim mode, a pipe is always text;
# In table mode, pipe is a cell delimiter unless it is escapedm.
# So we need to handle '\|' in BackslashMatcher and PipeMatcher won't see escaped pipe.
# Therefore, PipeMatcher always know a vertical bar is cell delimiter.
# In PipeMatcher, how do we distinguish if a pipe is first or last?
# Use openers?
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

class ParseResult(NamedTuple):
    line_finished: bool
    end_line: LineContext # the line and position the parsing stops. To boot next round of parsing, perform end_line.pos + 1.

class InlineParser:
    def __init__(self, cursor: Cursor):
        self.state = InlineState(cursor)
        self.matchers = MATCHERS
        self._attribute_parser: AttributeParser | None = None

    @property
    def in_verbatim(self) -> bool:
        return self.state.verbatim_len > 0

    def get_attribute_parser(self) -> AttributeParser:
        if self._attribute_parser is None:
            self._attribute_parser = AttributeParser(self.state.cursor)

        return self._attribute_parser

    def clear_attribute_parser(self):
        self._attribute_parser = None

    def _single_char(self, pos: int) -> int:
        self.state.events.append(
            Event.str(pos, pos)
        )
        return pos + 1

    def iter_merged_events(self) -> Iterator[Event]:
    
        last_str: Optional[Event] = None # str cache.

        for current in self.get_matches():
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
            else:
                # Current event is str, and it is not adjacent to last str, 
                # yield it and cache the current event.
                yield last_str
                last_str = current

        if last_str:
            yield last_str

    def get_matches(self):

        """Get parsed events.
                
        Remove trailing softbreak and any spaces.

        If verbatim is not closed, it will be closed.
        """
        if self._attribute_parser:
            self.reparse_attributes()

        self.state.trim_softbreak()

        if not self.state.events:
            return []

        
        self.state.close_verbatim()

        return self.state.events

    def reparse_attributes(self):
        logger.debug(f'## Reparse attributes')
        spans = self.state.attribute_spans
        if not spans:
            logger.debug('No attribute spans saved. Stop reparsing.')
            return
        
        # If attribute parsing failed, turn pending Span to str.
        # This is only applicable to inline attributes.
        # When we reparse block attributes, there should be not Span elements.
        self.state.demote_span_to_str()

        # This should prevent LeftBraceMatcher from taking 
        # left brace char as attributes starting token.
        
        self.state.disable_attribute()
        logger.debug(f'Disable attribute parsing {self.state._attr_action}')
        

        for span in spans:
            logger.debug(f'Re-parse range: {span}')
            self._parse_text(span.start, span.end)

        # Revert attributes state to enabled so that following
        # attributes could be parsed as normal.
        self.state.enable_attribute()
        logger.debug(f'=== Reparse ends. Re-enabled attribute parsing: {self.state._attr_action}')
    
    def feed(self, startpos: int, endpos: int):
        pos = startpos
        while pos <= endpos:
            logger.debug(f'## {pos}: start parsing. Attribute action: {self.state._attr_action}\n')
            if self.state.in_attributes:
                pos = self._try_attribute(pos, endpos)
                continue
            else:
                newpos = self._parse_without_attributes(pos, endpos)
                if newpos > endpos:
                    break
                else:
                    pos = newpos

    def _try_attribute(self, pos: int, endpos: int) -> int:
        """
        Parse attributes

        Workfllow:
        LeftBraceMatcher -> Init AttributeParser -> Keep pos in place
        -> next loop in feed -> _parse_attribute()

        Args:
            pos (int): start position of {
            endpos (int): end position of line
        """
        logger.debug(f'### Parsing attributes\n')
        sp = pos

        attr_parser = self.get_attribute_parser()

        result = attr_parser.feed(sp, endpos)

        logger.debug(f'Attribute parsing result {result}')

        ep = result.position

        match result.status:
            case AttrStatus.DONE:

                attr_start = self.state.attribute_start

                if attr_start is not None:
                    self.state.push_event(
                        Event.enter( # The opening {
                            kind=InlineContainer.ATTR,
                            span=Range(attr_start, attr_start)
                        )
                    )

                # Transfer attribute events.
                self.state.extend_events(attr_parser.events)

                self.state.push_event(
                    Event.exit(
                        kind=InlineContainer.ATTR,
                        span=Range(result.position, result.position)
                    )
                )

                # restore state to prior to adding attribute parser
                self.state.exit_attribute()
                # Reset attribute parser.
                self.clear_attribute_parser()

                return result.position + 1
            case AttrStatus.FAIL:
                logger.debug(f'Parsing attribute failed. Save failed span {sp}~{ep}')
                self.state.add_attr_span(sp, ep)
                self.clear_attribute_parser()
                self.reparse_attributes()
                logger.debug(f'Resume parsing after failed attributes at {ep+1}')
                return ep + 1

            case AttrStatus.CONTINUE:
                self.state.add_attr_span(sp, ep)
                return ep + 1

    def _parse_text(self, pos: int, endpos: int):
        while pos <= endpos:
            newpos = self._parse_without_attributes(pos, endpos)
            if newpos > endpos:
                break
            else:
                pos = newpos
    

    def _parse_without_attributes(self, pos: int, endpos: int) -> int:
        pos = self._try_str_before_special(pos, endpos)
        if pos > endpos: # gobbled whole line
            return pos

        # if we get here, then pos points to some special char,
        # i.e. we have something interesting at pos
        # Why newline bofore verbatim?
        newpos = self._try_newline(pos, endpos)
        if newpos is not None:
            return newpos

        newpos = self._try_closing_verbatim(pos, endpos)
        if newpos is not None:
            return newpos

        return self._try_matcher(pos, endpos)


    
    def _try_str_before_special(self, pos: int, endpos: int) -> int:
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
        logger.debug(f'## {pos}: Feed str before special in range {pos}~{endpos}\n')
        next_special = self.state.cursor.find_special(pos, endpos)
        
        logger.debug(f'Found special at: {next_special}')

        newpos = endpos + 1 if next_special is None else next_special

        if newpos > pos:
            logger.debug(f'Add Str before special char in range {pos}~{newpos-1}')
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, newpos-1),
                    kind=InlineLeaf.STR
                )
            )

        return newpos

        
    def _try_newline(self, pos: int, endpos: int) -> Optional[int]:

        if self.state.cursor.is_newline(pos):
            logger.debug(f'{pos}: parse softbreak')
            self.state.events.append(
                Event.leaf(
                    span=Range(pos, pos),
                    kind=InlineLeaf.SOFT_BREAK,
                )
            )
            return pos + 1

        return None
                

    def _try_closing_verbatim(self, pos: int, endpos) -> Optional[int]:
        if not self.state.in_verbatim: # not in verbatim mode
            return None

        count = self.state.cursor.count_char('`', pos)

        # In verbatim string, the special char is not backtick.
        if count == 0:
            self.state.events.append(
                Event.str(pos, pos)
            )
            return pos + 1

        # backtick found
        endchar = pos + count - 1

        # Opening and closing delimiters should be equal.
        if count != self.state.verbatim_len:
            self.state.events.append(
                Event.str(pos, endchar)
            )
            return endchar + 1

        # Check for raw attribute
        m2 = self.state.cursor.find_raw_attribute(endchar+1, endpos)
        # `<sometag>foos</sometag>`{=html}
        if m2 and self.state.verbatim_type == VerbatimKind.VERBATIM: # raw
            self.state.events.append(
                Event.exit(
                    kind=self.state.verbatim_type,
                    span=Range(pos, endchar) # the backtick
                )
            )
            # An extra event for `=FORMAT`
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
                    kind=self.state.verbatim_type,
                    span=Range(pos, endchar)
                )
            )
            pos = endchar + 1

        self.state.reset_verbatim()
        return pos

    def _try_matcher(self, pos: int, endpos: int) -> int:
        logger.debug(f'## {pos}: Try matchers')
        ch = self.state.cursor.char_at(pos)
        if ch is None:
            raise Exception(f'char at {pos} is undefined')

        if ch in self.matchers:
            matcher = self.matchers[ch]
            logger.debug(f'Found matcher {matcher.__class__.__name__}')
            res = matcher(self.state, pos, endpos)
            logger.debug(f'Matcher result: {res}')
            if res is not None:
                return res

            pos = self._single_char(pos)
            logger.debug(f'{pos}: {ch} is not a delimiter. Fallback to single char')
            return pos

        logger.debug(f'{pos}: single char {ch}')

        return self._single_char(pos)
