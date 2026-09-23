from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    BlockLeaf,
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
        - Backslash before a space if parsed as non-breaking space.
        
        """
        # Inspect if backslash is followed by [ \t]*\r?\n
        line_end_pos = state.cursor.find_rest_of_line_blank_end(pos+1, endpos)
        # Hardbreak.
        if line_end_pos is not None:
            # see if there were preceding spaces and remove them.
            # Look like: `hello  \   \n`
            state.trim_last_str_span_trailing()

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
        
        # Check if backslash if followed by any punctuations.
        # You might write somthihg like
        # \!, \", \#, \%, \&
        m_punct = state.cursor.find_punctuation(pos+1, endpos)
        
        if m_punct is not None:
            # \ is escape
            state.events.append(
                Event.leaf(
                    Range(pos, pos), 
                    InlineLeaf.ESCAPE
                )
            )
            state.events.append(
                Event.leaf(
                    Range(m_punct.start, m_punct.end),
                    InlineLeaf.STR
                )
            )
            return m_punct.end + 1
        elif pos + 1 <= endpos and state.cursor.is_space(pos+1):
            # \<space> is non-breaking space
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
        else:
            # Plain \
            state.events.append(
                Event.leaf(
                    Range(pos, pos),
                    InlineLeaf.STR
                )
            )
            return pos+1