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
        # (
        if not state.destination:
            return None
        state.add_opener('(', Event.leaf(Range(pos, pos), InlineLeaf.STR))
        return pos+1