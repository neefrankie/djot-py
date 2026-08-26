from dataclasses import dataclass
from enum import Enum
import re
from typing import List

from .event import Event


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

re_key_char = re.compile(r'[a-zA-Z0-9_:-]')

def is_key_char(c: str) -> bool:
    return bool(re_key_char.match(c))

# Characters that should not appear in an id
_re_forbidden_id_chars = re.compile(
    r'^[^\]\[~!@#$%^&*(){}`,.<>\\|=+/?\s]'
)

_re_leading_space = re.compile(r'^\s')

_re_leading_word = re.compile(r'^\w')

class ParseStatus(Enum):
    DONE = 0
    FAIL = 1
    CONTINUE = 2

@dataclass(frozen=True)
class ParseResult:
    status: ParseStatus
    position: int

    def is_done(self) -> bool:
        return self.status == ParseStatus.DONE
    
    def is_fail(self) -> bool:
        return self.status == ParseStatus.FAIL
    
    def is_continue(self) -> bool:
        return self.status == ParseStatus.CONTINUE


class AttributeParser:
    def __init__(self, subject: str):
        self.subject = subject
        self.state = State.START
        self.begin: int | None = None
        self.lastpos: int | None = None
        self.matches: List[Event] = []

    def add_event(self, event: Event):
        self.matches.append(event)

    def feed(self, startpos: int, endpos: int) -> ParseResult:
        """
        Equivalent to js version AttributeParser.feed
        """
        pos = startpos
        while pos <= endpos:
            self.state = self.handle(self.state, pos)
            if self.state == State.DONE:
                return ParseResult(
                    status=ParseStatus.DONE, 
                    position=pos
                )
            elif self.state == State.FAIL:
                self.lastpos = pos
                return ParseResult(
                    status=ParseStatus.FAIL, 
                    position=pos
                )
            else:
                self.lastpos = pos
                pos += 1

        return ParseResult(
            status=ParseStatus.CONTINUE, 
            position=endpos
        )


    def handle(self, state: State, pos: int) -> State:
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
        if self.subject[pos] == '{':
            return State.SCANNING
        else:
            return State.FAIL
        
    def _scanning(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING]
        """
        c = self.subject[pos]
        if c == '\n' or c == '\r':
            return State.SCANNING
        elif c == ' ' or c == '\t':
            self.add_event(
                Event(
                    startpos=pos,
                    endpos=pos,
                    annot='attr_space'
                )
            )
            return State.SCANNING
        elif c == '}':
            return State.DONE
        elif c == '#':
            # self.begin point to #
            self.begin = pos
            self.add_event(
                Event(
                    startpos=pos,
                    endpos=pos,
                    annot='attr_id_start'
                )
            )
            return State.SCANNING_ID
        elif c == '%':
            # self.begin point to %
            self.begin = pos
            return State.SCANNING_COMMENT
        elif c == '.':
            self.begin = pos
            self.add_event(
                Event(
                    startpos=pos,
                    endpos=pos,
                    annot='attr_class_start'
                )
            )
            return State.SCANNING_CLASS
        elif is_key_char(c):
            self.begin = pos
            return State.SCANNING_KEY
        else:
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
        c = self.subject[pos]
        # c might be start of comment or end of comment
        if c == '%':
            # If pos is at the start of comment, begin == pos.
            if self.begin is not None and pos > self.begin:
                self.add_event(
                    Event(
                        startpos=self.begin,
                        endpos=pos,
                        annot='comment'
                    )
                )
            return State.SCANNING
        elif c == '}':
            # Comment extending to end of attribute list
            return State.DONE
        else:
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
        c = self.subject[pos]

        # As long as the current character is in allowed characters, keep scanning.
        if _re_forbidden_id_chars.search(c) is not None:
            return State.SCANNING_ID
        # None-id characters
        # } indicates the end of attribute list.
        elif c == '}':
            if self.begin and self.lastpos and self.lastpos > self.begin:
                self.add_event(
                    Event(
                        startpos=self.begin + 1,
                        endpos=self.lastpos,
                        annot='id'
                    )
                )
            self.begin = None
            return State.DONE
        # Space indicates next attribute will appear.
        elif _re_leading_space.search(c) is not None:
            # the id is ended.
            if self.begin and self.lastpos and self.lastpos > self.begin:
                self.add_event(
                    Event(
                        startpos=self.begin + 1,
                        endpos=self.lastpos,
                        annot='id'
                    )
                )
            # if current character is space but not newline.
            if not (c == '\r' or c == '\n'):
                self.add_event(
                    Event(
                        startpos=pos,
                        endpos=pos,
                        annot='attr_space'
                    )
                )
            # Prepare to scan next attribute.
            self.begin = None
            return State.SCANNING
        else:
            return State.FAIL

    def _scanning_class(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_CLASS]

        Example:

        .foo .bar
        .foo }
        """
        c = self.subject[pos] # c points to the position after dot.
        if _re_leading_word.search(c) is not None or c == '_' or c == '-' or c == ':':
            return State.SCANNING_CLASS
        elif c == '}':
            if self.begin and self.lastpos and self.lastpos > self.begin:
                self.add_event(
                    Event(
                        startpos=self.begin + 1,
                        endpos=self.lastpos,
                        annot='class'
                    )
                )
            self.begin = None
            return State.DONE
        elif _re_leading_space.search(c) is not None: # space
            if self.begin and self.lastpos and self.lastpos > self.begin:
                self.add_event(
                    Event(
                        startpos=self.begin + 1,
                        endpos=self.lastpos,
                        annot='class',
                    )
                )
            if not (c == '\r' or c == '\n'):
                self.add_event(
                    Event(
                        startpos=pos,
                        endpos=pos,
                        annot='attr_space'
                    )
                )
            self.begin = None
            return State.SCANNING
        else:
            return State.FAIL

    def _scanning_key(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_KEY]
        
        Example:
        
        foo=bar
        foo=bar}
        foo=bar
        """
        c = self.subject[pos]
        if c == '=' and self.begin and self.lastpos:
            self.add_event(
                Event(
                    startpos=self.begin,
                    endpos=self.lastpos,
                    annot='key'
                )
            )
            self.add_event(
                Event(
                    startpos=pos,
                    endpos=pos,
                    annot='attr_equal_markder'
                )
            )
            self.begin = None
            return State.SCANNING_VALUE
        elif is_key_char(c):
            return State.SCANNING_KEY
        else:
            return State.FAIL
        
    def _scanning_value(self, pos: int) -> State:
        c = self.subject[pos]
        if c == '"':
            self.begin = pos
            self.add_event(
                Event(
                    startpos=pos,
                    endpos=pos,
                    annot='attr_quote_marker'
                )
            )
            return State.SCANNING_QUOTED_VALUE
        elif is_key_char(c):
            self.begin = pos
            return State.SCANNING_BARE_VALUE
        else:
            return State.FAIL
        
    def _scanning_bare_value(self, pos: int) -> State:
        c = self.subject[pos]
        if is_key_char(c):
            return State.SCANNING_BARE_VALUE
        elif c == '}' and self.begin and self.lastpos:
            self.add_event(
                Event(
                    startpos=self.begin,
                    endpos=self.lastpos,
                    annot='value'
                )
            )
            self.begin = None
            return State.DONE
        elif _re_leading_space.search(c) and self.begin and self.lastpos:
            self.add_event(
                Event(
                    startpos=self.begin,
                    endpos=self.lastpos,
                    annot='value'
                )
            )
            if not (c == '\r' or c == '\n'):
                self.add_event(
                    Event(
                        startpos=pos,
                        endpos=pos,
                        annot='attr_space'
                    )
                )
            self.begin = None
            return State.SCANNING
        else:
            return State.FAIL
        
    def _scanning_escaped(self, pos: int) -> State:
        return State.SCANNING_QUOTED_VALUE
    
    def _scanning_escaped_in_continuation(self, pos: int) -> State:
        return State.SCANNING_QUOTED_VALUE_CONTINUATION
    
    def _scanning_quoted_value(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_QUOTED_VALUE]
        """
        c = self.subject[pos]
        if c == '"' and self.begin and self.lastpos:
            self.add_event(
                Event(
                    startpos=self.begin+1,
                    endpos=self.lastpos,
                    annot='value'
                )
            )
            self.add_event(
                Event(
                    startpos=pos,
                    endpos=pos,
                    annot='attr_quote_marker'
                )
            )
            self.begin = None
            return State.SCANNING
        
        elif c == '\n' and self.begin and self.lastpos:
            self.add_event(
                Event(
                    startpos=self.begin+1,
                    endpos=self.lastpos,
                    annot='value'
                )
            )
            self.begin = None
            return State.SCANNING_QUOTED_VALUE_CONTINUATION
        elif c == '\\':
            return State.SCANNING_ESCAPED
        else:
            return State.SCANNING_QUOTED_VALUE
        
    def _scanning_quoted_value_continuation(self, pos: int) -> State:
        """
        Equivalent to js version handlers[State.SCANNING_QUOTED_VALUE_CONTINUATION]
        """
        c = self.subject[pos]
        if self.begin is None:
            self.begin = pos

        if c == '"' and self.begin and self.lastpos:
            self.add_event(
                Event(
                    startpos=self.begin,
                    endpos=self.lastpos,
                    annot='value'
                )
            )
            self.add_event(
                Event(
                    startpos=pos,
                    endpos=pos,
                    annot='attr_quote_marker'
                )
            )
            self.begin = None
            return State.SCANNING
        elif c == '\n' and self.begin and self.lastpos:
            self.add_event(
                Event(
                    startpos=self.begin,
                    endpos=self.lastpos,
                    annot='value'
                )
            )
            self.begin = None
            return State.SCANNING_QUOTED_VALUE_CONTINUATION
        elif c == '\\':
            return State.SCANNING_ESCAPED_IN_CONTINUATION
        else:
            return State.SCANNING_QUOTED_VALUE_CONTINUATION
            

