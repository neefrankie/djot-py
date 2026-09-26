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

class PeriodMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        """Possible ellipses

        A sequence of three periods is parsed as ellipses
        
        """
        if state.cursor.has_two_period(pos+1, endpos): # find two more periods after current dot.
            state.events.append(
                Event.leaf(
                    Range(pos, pos+2),
                    InlineLeaf.ELLIPSES
                )
            )
            return pos+3
        
        return None