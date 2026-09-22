"""
Parser for attributes, implemented as a state machine.

attributes { id = "foo", class = "bar baz",
             key1 = "val1", key2 = "val2" }

syntax:

attributes <- '{' whitespace* attribute (whitespace attribute)* whitespace* '}'

attribute <- identifier | class | keyval

identifier <- '#' name

class <- '.' name

name <- (nonspace, nonpunctuation other than ':', '_', '-')+

key <- (ASCII_ALPHANUM } | ':' | '_' | '-')+

val <- bareval | quotevdval

bareval <- (ASCII_ALPHANUM | '.' | '-' | '_')+

quotedval <- '"' ([^"] | '\"') '"'
"""

import string
from dataclasses import dataclass
from enum import Enum
import re
from typing import Final, List

from .event import Event, AttrKind
from .input import InputText
from .common import Range

# states
class State(Enum):
    SCANNING = 0
    SCANNING_ID = 1
    SCANNING_CLASS = 2
    SCANNING_KEY = 3
    SCANNING_VALUE = 4
    SCANNING_BARE_VALUE = 5
    SCANNING_QUOTED_VALUE = 6
    SCANNING_QUOTED_VALUE_CONTINUATION = 7
    SCANNING_ESCAPED = 8
    SCANNING_ESCAPED_IN_CONTINUATION = 9
    SCANNING_COMMENT = 10
    FAIL = 11
    DONE = 12
    START = 13


# In Python, str.isalnum() includes isalpha(), isdecimal(), isdigit().
# They are not exactly identifical to regex defined in djot.js:
# r'[a-zA-Z0-9_:-]'
# For isalpha, 'µ'.isalpha() since non-ASCII characters can be considered alphabetical too
# For isdecimal and isdigit, number in other language is also true
# This actually equals string.ascii_letters + string.digits + '_:-'
# Here's a strict version of ASCII char set permitted in key, bare value, id/class value.
# Corresponds to regex r'[a-zA-Z0-9_:-]'
_ASCII_ATTR_CHARS: Final = frozenset(string.ascii_letters + string.digits + "_:-")

def is_ascci_attr_char(c: str) -> bool:
    return c in _ASCII_ATTR_CHARS


class AttrFlowControl(Enum):
    DONE = 0
    FAIL = 1
    CONTINUE = 2 # TODO: remove this to disable newline inside attributes.

@dataclass(slots=True, frozen=True)
class AttrParseResult:
    status: AttrFlowControl # TODO: if AttrFlowControl has only DONE and FAIL, is this still needed?
    position: int

    def is_done(self) -> bool:
        return self.status == AttrFlowControl.DONE
    
    def is_fail(self) -> bool:
        return self.status == AttrFlowControl.FAIL
    
    def is_continue(self) -> bool:
        return self.status == AttrFlowControl.CONTINUE


class AttributeParser:
    def __init__(self, cursor: InputText):
        self.cursor = cursor
        self.state = State.START
        self.begin: int | None = None # the begin position of a token
        self.lastpos: int | None = None # tracks the last position current char
        self.events: List[Event] = []

    def add_event(self, event: Event):
        self.events.append(event)

    def feed(self, startpos: int, endpos: int) -> AttrParseResult:
        """
        Equivalent to js version AttributeParser.feed
        """
        pos = startpos
        while pos <= endpos:
            self.state = self.step(self.state, pos)
            if self.state == State.DONE:
                return AttrParseResult(
                    status=AttrFlowControl.DONE, 
                    position=pos
                )
            elif self.state == State.FAIL:
                self.lastpos = pos
                return AttrParseResult(
                    status=AttrFlowControl.FAIL, 
                    position=pos
                )
            else:
                self.lastpos = pos
                pos += 1

        # If state is neither DONE nor FAIL, and endpos is reached,
        # return CONTINUE to tell main parser that parsing should continue
        # to next line.
        # However, I want don't want to support newline inside attribute.
        # Keep attributes on one line.
        return AttrParseResult(
            status=AttrFlowControl.CONTINUE, # TODO: to forbid newline in attributes, should we return FAIL?
            position=endpos
        )


    def step(self, state: State, pos: int) -> State:
        """
        Equivalent to js version handlers array.
        """
        match state:
            case State.START:
                return self._start(pos)
            case State.FAIL:
                return State.FAIL
            case State.DONE:
                return State.DONE
            case State.SCANNING:
                return self._scanning(pos)
            case State.SCANNING_COMMENT:
                return self._scanning_comment(pos)
            case State.SCANNING_ID:
                # Point to position after #
                return self._scanning_id(pos)
            case State.SCANNING_CLASS:
                return self._scanning_class(pos)
            case State.SCANNING_KEY:
                return self._scanning_key(pos)
            case State.SCANNING_VALUE:
                return self._scanning_value(pos)
            case State.SCANNING_BARE_VALUE:
                return self._scanning_bare_value(pos)
            case State.SCANNING_ESCAPED:
                return self._scanning_escaped(pos)
            case State.SCANNING_ESCAPED_IN_CONTINUATION:
                return self._scanning_escaped_in_continuation(pos)
            case State.SCANNING_QUOTED_VALUE:
                return self._scanning_quoted_value(pos)
            case _:
                raise Exception(f"Invalid state: {state}")

    def _start(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.START]
        START -> SCANNING
        """
        if self.cursor.src[pos] == '{':
            return State.SCANNING
        else:
            return State.FAIL
        
    def _scanning(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING]
        """
        ch = self.cursor.src[pos]
        match ch:
            case '\n' | '\r': # TODO: does this mean supporting newline? what if we disallow newline?
                return State.SCANNING
            case ' ' | '\t':
                self.add_event(
                    Event.attr(
                        Range(pos, pos),
                        AttrKind.SPACE
                    )
                )
                return State.SCANNING # Current pos is space, continue scanning
            case '}':
                return State.DONE
            case '#':
                # self.begin point to #
                self.begin = pos
                self.events.append(
                    Event.attr(
                        Range(pos, pos), 
                        AttrKind.ID_START
                    )
                )
                return State.SCANNING_ID
            case '%':
                # self.begin point to %
                self.begin = pos
                return State.SCANNING_COMMENT
            case '.':
                self.begin = pos
                self.add_event(
                    Event.attr(
                        Range(pos, pos),
                        AttrKind.CLASS_START
                    )
                )
                return State.SCANNING_CLASS
            case _ if is_ascci_attr_char(ch):
                self.begin = pos
                return State.SCANNING_KEY
            case _:
                return State.FAIL
        
    def _scanning_comment(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_COMMENT]
        
        Example:

        % foo bar }
        % foo bar %
                            ⃔
        SCANNING -> SCANNING_COMMENT -> DONE
          |<-----------|
        """
        ch = self.cursor.src[pos]
        # Already in comment, `%` or `}` mean end of comment
        match ch:
            case '%':
                # If pos is at the start of comment, begin == pos.
                if self.begin is not None and pos > self.begin:
                    self.add_event(
                        Event.attr(
                            Range(self.begin, pos),
                            AttrKind.COMMENT
                        )
                    )
                return State.SCANNING
            case '}':
                # Comment extending to end of attribute list
                return State.DONE
            case _:
                # In the middle of comment
                return State.SCANNING_COMMENT
        
    def _scanning_id(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_ID]

        Example:

        #foo<space>
        #foo}
        """
        # start from position after #
        # For exmaple, pos points to f in #foo
        ch = self.cursor.src[pos]

        # As long as the current character is in allowed characters, keep scanning.
        if is_ascci_attr_char(ch):
            return State.SCANNING_ID

        # } indicates the end of attribute list.
        if ch == '}':
            if self.begin and self.lastpos and self.lastpos > self.begin: # has content
                self.add_event(
                    Event.attr(
                        Range(self.begin + 1, self.lastpos),
                        AttrKind.ID
                    )
                )
            self.begin = None
            return State.DONE

        # Space indicates current id attrbute ends.
        if ch.isspace():
            # the id is ended.
            if self.begin and self.lastpos and self.lastpos > self.begin: # content
                self.add_event(
                    Event.attr(
                        Range(self.begin + 1, self.lastpos), # begin points to #
                        AttrKind.ID
                    )
                )
            # if current character is space but not newline. Why save space?
            # TODO: How to handle it if we disallow newline?
            if not (ch == '\r' or ch == '\n'):
                self.add_event(
                    Event.attr(
                        Range(pos, pos), 
                        AttrKind.SPACE
                    )
                )
            # Prepare to scan next attribute.
            self.begin = None
            return State.SCANNING
        
        return State.FAIL

    def _scanning_class(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_CLASS]

        Example:

        .foo .bar
        .foo }
        """
        ch = self.cursor.src[pos] # c points to the position after dot.

        if is_ascci_attr_char(ch):
            return State.SCANNING_CLASS

        if ch == '}':
            if self.begin and self.lastpos and self.lastpos > self.begin:
                self.add_event(
                    Event.attr(
                        Range(self.begin + 1, self.lastpos),
                        kind=AttrKind.CLASS
                    )
                )
            self.begin = None
            return State.DONE

        if ch.isspace(): # space
            if self.begin and self.lastpos and self.lastpos > self.begin:
                self.add_event(
                    Event.attr(
                        Range(self.begin + 1, self.lastpos),
                        kind=AttrKind.CLASS,
                    )
                )
            if not (ch == '\r' or ch == '\n'):
                self.add_event(
                    Event.attr(
                        Range(pos, pos),
                        kind=AttrKind.SPACE
                    )
                )
            self.begin = None
            return State.SCANNING
        
        return State.FAIL

    def _scanning_key(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_KEY]
        """
        ch = self.cursor.src[pos] # now pos to a ascii alphanumeric character.

        if ch == '=' and self.begin and self.lastpos:
            self.add_event( # before = it is key
                Event.attr(
                    Range(self.begin, self.lastpos),
                    kind=AttrKind.KEY
                )
            )
            self.add_event( # =
                Event.attr(
                    Range(pos, pos),
                    kind=AttrKind.EQUAL_MARKER
                )
            )
            self.begin = None
            return State.SCANNING_VALUE

        if is_ascci_attr_char(ch):
            return State.SCANNING_KEY
        
        return State.FAIL
        
    def _scanning_value(self, pos: int) -> State:
        ch = self.cursor.src[pos] # pos points to the char after =

        if ch == '"': # quoted value
            self.begin = pos
            self.add_event( # "
                Event.attr(
                    Range(pos, pos),
                    kind=AttrKind.QUOTE_MARKER
                )
            )
            return State.SCANNING_QUOTED_VALUE

        if is_ascci_attr_char(ch): # bare value
            self.begin = pos
            # TODO: # does _scanning_bare_value points to the second char after here?
            # For example, `foo=bar`, upon entering _scanning_value, pos points to `b`.
            # And then pos += 1, so when we call _scanning_bare_value, pos points to `a`.
            return State.SCANNING_BARE_VALUE 
        
        return State.FAIL
        
    def _scanning_bare_value(self, pos: int) -> State:
        ch = self.cursor.src[pos]

        if is_ascci_attr_char(ch):
            return State.SCANNING_BARE_VALUE

        if ch == '}' and self.begin and self.lastpos:
            self.add_event(
                Event.attr(
                    Range(self.begin, self.lastpos),
                    kind=AttrKind.VALUE
                )
            )
            self.begin = None
            return State.DONE

        if ch.isspace() and self.begin and self.lastpos: # finished key=value
            self.add_event(
                Event.attr(
                    Range(self.begin, self.lastpos),
                    kind=AttrKind.VALUE
                )
            )
            if not (ch == '\r' or ch == '\n'): # TODO: disalloww newline.
                self.add_event(
                    Event.attr(
                        Range(pos, pos),
                        kind=AttrKind.SPACE
                    )
                )
            self.begin = None
            return State.SCANNING
        
        return State.FAIL
        
    def _scanning_escaped(self, pos: int) -> State:
        return State.SCANNING_QUOTED_VALUE
    
    def _scanning_escaped_in_continuation(self, pos: int) -> State:
        return State.SCANNING_QUOTED_VALUE_CONTINUATION
    
    def _scanning_quoted_value(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_QUOTED_VALUE]
        """
        ch = self.cursor.src[pos]
        if ch == '"' and self.begin and self.lastpos: # closing "
            self.add_event(
                Event.attr(
                    Range(self.begin+1, self.lastpos),
                    kind=AttrKind.VALUE
                )
            )
            self.add_event(
                Event.attr(
                    Range(pos, pos),
                    kind=AttrKind.QUOTE_MARKER
                )
            )
            self.begin = None
            return State.SCANNING
        
        elif ch == '\n' and self.begin and self.lastpos: # TODO: forbid newline.
            self.add_event(
                Event.attr(
                    Range(self.begin+1, self.lastpos),
                    kind=AttrKind.VALUE
                )
            )
            self.begin = None
            return State.SCANNING_QUOTED_VALUE_CONTINUATION
        elif ch == '\\':
            return State.SCANNING_ESCAPED
        else:
            return State.SCANNING_QUOTED_VALUE
        
    def _scanning_quoted_value_continuation(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_QUOTED_VALUE_CONTINUATION]
        """
        ch = self.cursor.src[pos]
        if self.begin is None:
            self.begin = pos

        if ch == '"' and self.begin and self.lastpos: # closing "
            self.add_event(
                Event.attr(
                    Range(self.begin, self.lastpos),
                    kind=AttrKind.VALUE
                )
            )
            self.add_event(
                Event.attr(
                    Range(pos, pos),
                    kind=AttrKind.QUOTE_MARKER
                )
            )
            self.begin = None
            return State.SCANNING
        elif ch == '\n' and self.begin and self.lastpos: # TODO: forbid newline.
            self.add_event(
                Event.attr(
                    Range(start=self.begin,
                    end=self.lastpos),
                    kind=AttrKind.VALUE
                )
            )
            self.begin = None
            return State.SCANNING_QUOTED_VALUE_CONTINUATION
        elif ch == '\\':
            return State.SCANNING_ESCAPED_IN_CONTINUATION
        else:
            return State.SCANNING_QUOTED_VALUE_CONTINUATION
            

