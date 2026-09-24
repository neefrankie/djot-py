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

NOTE: this is the original js doc. My impelementation does not support newline and comment in attributes.
"""

import string
from dataclasses import dataclass
from enum import Enum
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
    SCANNING_ESCAPED = 8
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

@dataclass(slots=True, frozen=True)
class AttrParseResult:
    status: AttrFlowControl # TODO: if AttrFlowControl has only DONE and FAIL, is this still needed?
    position: int # Last position the state machine stops.

    def is_done(self) -> bool:
        return self.status == AttrFlowControl.DONE
    
    def is_fail(self) -> bool:
        return self.status == AttrFlowControl.FAIL


class AttributeParser:
    """Parse block or inline attributes.

    This implementation differs from djot specification.

    Original specification on attributes are as follows:

    ## Inline attributes

    Attributes are put inside curaly braces and must immediately
    follow the inline element to which they are attached (with no
    intervening whitespace).

    % begins a comenet, which ends with the next % or the end of
    the attrbute `}`

    Attribute specifiers may contain line breaks.

    Example:

    ```
    An attribute on _emphasis text_{# foo
    .bar .baz key="my value"}

    avant{lang=fr}{.blue}
    ```
    
    ## Block attributes
    
    A line immediately before the block.
    Block attributes have the same syntax as inline attributes,
    but if they don't fit on one line, subsequence lines must be indented.
    Repeated attribute specifiers can be used, and the attributes
    will accumulate.

    
    {#water}
    {.important .large}
    Don't forget to turn off the water.


    ## My restriction on attributes.

    Permitting line break inside attributes causes a lot trouble
    to implement. You have to use a lot of backtracing,
    which is against the spirit of djot.

    I guess the cause of the problem comes from comment. It looks like this with comment inside attributes:

    ```
    {#ident % later we'll add a class % }
    ```

    Whe there is only comment in attributes, it degrades to
    a comment-only attribute. That's why `{% ... %}` serve as
    a general way to add comment.
    When you write a comment-only attribute, you naturally want
    to have line breaks.
    This approach make `{ }` serving totally different purposes. 
    What's more, there is a repetition for block attributes.
    Repeated attribute specifiers play the same role line breaks
    in attribute.
    If we really want to support continuation to another line, 
    why not use another `{ }` on a new line? 
    Multiple lines of `{ }` is much easier to parse.

    Comment in attributes causes a lot trouble.
    In reality, it's not a must-have feature.
    So I decided to restrcit attribute on one line,
    and no comment in attributes.

    This will greatly simplify the implementation.
    Whenever a `{` appeared, feed it to the the end of line.
    If closing `}` is not found, it's a fail.
    """

    _SPACE_TAB = ' \t'

    def __init__(self, cursor: InputText):
        self.cursor = cursor
        self.state = State.START
        self.begin: int | None = None # the begin position of a token
        self.lastpos: int | None = None # tracks the last position current char

        # Events collected while scanning.
        # Events emitted while seeing:
        # - space
        # - #
        # - .
        # - }
        # - "
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
            # State turned to DONE only when pos points to `}`
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

        # Default to FAIL.
        # This differs from js version, which returns CONTINUE to support newline in attributes.
        return AttrParseResult(
            status=AttrFlowControl.FAIL,
            position=pos
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
            case State.SCANNING_ID:
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
        # Here it differs from js version. We don't permit newline.
        if ch in self._SPACE_TAB: 
            # the id is ended.
            if self.begin and self.lastpos and self.lastpos > self.begin: # content
                self.add_event(
                    Event.attr(
                        Range(self.begin + 1, self.lastpos), # begin points to #
                        AttrKind.ID
                    )
                )

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

        if ch in self._SPACE_TAB: # Differs from js vesion. We don't permit newline.
            if self.begin and self.lastpos and self.lastpos > self.begin:
                self.add_event(
                    Event.attr(
                        Range(self.begin + 1, self.lastpos),
                        kind=AttrKind.CLASS,
                    )
                )
            
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
            self.begin = pos # begin points to "
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

        # It differs from js version. We don't permit newline.
        if ch in self._SPACE_TAB and self.begin and self.lastpos: # finished key=value
            self.add_event(
                Event.attr(
                    Range(self.begin, self.lastpos),
                    kind=AttrKind.VALUE
                )
            )
            
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
    
    def _scanning_quoted_value(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_QUOTED_VALUE]
        """
        ch = self.cursor.src[pos]
        if ch == '"' and self.begin and self.lastpos: # closing "
            self.add_event(
                Event.attr(
                    Range(self.begin+1, self.lastpos), # begin + 1 jumps over "
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

        # Here it dffers from js version. We don't permit newline.
        if ch in '\r\n' and self.begin and self.lastpos:
            return State.FAIL

        if ch == '\\':
            return State.SCANNING_ESCAPED
        
        return State.SCANNING_QUOTED_VALUE
            

