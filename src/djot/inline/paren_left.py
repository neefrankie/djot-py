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

class LeftParenMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        # If we are not entering link mode, this is a plain text.
        if not state.destination:
            return None

        # If we are already in link mode, the opening paren is
        # aleady consumed by RightBracketMatcher.
        # So if we see another opening paren, it should be treated as plain text.
        state.add_opener('(', Event.leaf(Range(pos, pos), InlineLeaf.STR))
        return pos+1