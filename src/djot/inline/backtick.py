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
        count = state.cursor.count_char('`', pos)
        if count == 0:
            return None
        
        endchar = pos + count - 1

        # $$` x^n + y^n = z^n `
        # If previous two characters are $$, and not preceded by a backslash,
        # it's a display math.
        if state.cursor.has_double_dollars(pos-2) and (not state.cursor.is_backslash(pos-3)):
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
            state.set_verbatim(pos, endchar, VerbatimKind.DISPLAY_MATH)
            return endchar+1

        # Inline match.
        # it might be:
        # - \$$
        # - $
        # - other text
        # What about \\$$?
        if state.cursor.has_single_dollar(pos-1):
            # Merge the single dollar with current token.
            state.events.pop() # remove $
            state.events.append(
                Event.enter(
                    Range(pos-1, endchar),
                    kind=VerbatimKind.INLINE_MATH,
                )
            )
            # Entering into inline math mode.
            state.set_verbatim(pos, endchar, VerbatimKind.INLINE_MATH)
            return endchar+1
        
        # Plain verbatim
        state.events.append(
            Event.enter(
                Range(pos, endchar),
                kind=VerbatimKind.VERBATIM,
            )
        )
        
        state.set_verbatim(pos, endchar, VerbatimKind.VERBATIM)
        return endchar+1 # after `