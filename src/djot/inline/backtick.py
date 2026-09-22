from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    VerbatimKind,
)
from .matcher import Matcher
from .state import InlineState

class BacktickMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        # Find zero or more backtick
        m = state.cursor.find_opening_backtick(pos, endpos)
        if m is None:
            return None
        
        # Now we have opening backtick.
        endchar = m.end # position of last found backtick
        # $$` x^n + y^n = z^n `
        # If previous two characters are $$, and not preceded by a backslash,
        # it's a display math.
        if state.cursor.find_double_dollar(pos-2) and (not state.cursor.find_backslash(pos-3)):
            # Merge previous 2 dollar sign with current token.
            state.events.pop() # remove first $
            state.events.pop() # remove second $
            # $$`
            state.events.append(
                Event.enter(
                    Range(pos-2, endchar),
                    kind=VerbatimKind.DISPLAY_MATH,
                )
            )
            # Entering into display math mode.
            state.verbatim_type = VerbatimKind.DISPLAY_MATH
        # it might be:
        # - \$$
        # - $
        # - other text
        # What about \\$$?
        elif state.cursor.find_single_dollar(pos-1):
            # Merge the single dollar with current token.
            state.events.pop() # remove $
            state.events.append(
                Event.enter(
                    Range(pos-1, endchar),
                    kind=VerbatimKind.INLINE_MATH,
                )
            )
            # Entering into inline math mode.
            state.verbatim_type = VerbatimKind.INLINE_MATH
        else:
            state.events.append(
                Event.enter(
                    Range(pos, endchar),
                    kind=VerbatimKind.VERBATIM,
                )
            )
            # Plain verbatim
            state.verbatim_type = VerbatimKind.VERBATIM
        state.verbatim_len = endchar - pos + 1 # length of backticks.
        return endchar+1 # after `