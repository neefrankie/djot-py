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

class LeftBracketMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        """Note reference
        
        A foonote reference is ^ + reference label in square brackets

        Example:

        Here is the reference.[^foo]
        """
        # \^([^\]]+)\]
        m = state.cursor.find_note_reference(pos+1, endpos) # test from ^
        if m:
            state.events.append(
                Event.leaf(
                    Range(pos, m.end),
                    InlineLeaf.FOOTNOTE_REF
                )
            )
            return m.end+1
        else:
            state.add_opener(
                '[',
                Event.leaf(
                    Range(pos, pos),
                    InlineLeaf.STR
                )
            )
            return pos+1