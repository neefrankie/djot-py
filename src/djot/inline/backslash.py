from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    InlineLeaf,
)
from .matcher import Matcher
from .state import InlineState

class BackslashMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        """Backslash in Djot

        All ASCII punctuation characters may be backslah-escaped.

        Backslashes before characters other than ASCII punctuation characters
        are just treated as literal backslashes, with the following exceptions:

        - Backslash before a newline (or before spaces or tabs followed by a newline) is parsed as a hard line break.
        - Backslash before a space is parsed as non-breaking space.
        
        """
        # Inspect if backslash is followed by [ \t]*\r?\n
        line_end_pos = state.cursor.find_blank_end(pos+1, endpos)
        # Hardbreak.
        if line_end_pos is not None:
            # see if there were preceding spaces and remove them.
            # Look like: `hello  \   \n`
            state.trim_last_event_if_str()

            # \ is escape
            state.events.append(
                Event.leaf(
                    Range(pos, pos),
                    InlineLeaf.ESCAPE
                )
            )
            # The following is hard break.
            state.events.append(
                Event.leaf(
                    Range(pos+1, line_end_pos),
                    InlineLeaf.HARD_BREAK
                )
            )
            return line_end_pos + 1 # new pos starts after newline.
        
        # Check if backslash is followed by any punctuations.
        # You might write somthihg like
        # \!, \", \#, \%, \&
        next_pos = pos + 1
        
        if state.cursor.is_ascii_punct(next_pos):
            # \ is escape
            state.events.append(
                Event.leaf(
                    Range(pos, pos), 
                    InlineLeaf.ESCAPE
                )
            )
            state.events.append(
                Event.leaf(
                    Range(next_pos, next_pos),
                    InlineLeaf.STR
                )
            )
            return next_pos + 1

        # non-breaking space
        if pos + 1 <= endpos and state.cursor.is_space(pos+1):
            state.events.append(
                Event.leaf(
                    Range(pos, pos),
                    InlineLeaf.ESCAPE
                )
            )
            state.events.append(
                Event.leaf(
                    Range(pos+1, pos+1),
                    InlineLeaf.NBSP
                )
            )
            return pos+2
        
        # Plain \
        state.events.append(
            Event.leaf(
                Range(pos, pos),
                InlineLeaf.STR
            )
        )
        return pos+1