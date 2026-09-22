from ..common import (
    Range,
)
from ..event import (
    Event,
    InlineContainer,
    InlineLeaf
)
from ..input import InputText
from .state import InlineState
from .between import BetweenMatcher

class HyphenMatcher(BetweenMatcher):

    def __init__(self):
        super().__init__(
            ch='-', 
            container_kind=InlineContainer.DELETE, 
            fallback_leaf=InlineLeaf.STR,
        )

    def can_open(self, cursor: InputText, pos: int) -> bool:
        return cursor.has_brace(pos)

    def __call__(self, state: InlineState, pos: int, endpos: int) -> int | None:

        # {-delete-}
        if state.cursor.is_left_brace(pos-1) or state.cursor.is_right_brace(pos+1): # {- or -}
            newpos = super().__call__(state, pos, endpos)
            
            if newpos:
                return newpos
            
        # Didn't match a del, try for smart hyphen.
        ep = pos
        hyphens = 0
        while ep <= endpos and state.cursor.char_at(ep) == '-':
            ep += 1 # if pos == endpos, only one loop
            hyphens += 1

        if state.cursor.char_at(ep) == '}': # -}
            hyphens -= 1 # last hyphen is close del

        if hyphens == 0: # this means we have '-}'
            state.events.append(Event.leaf(Range(pos, pos+1), InlineLeaf.STR))
            return pos+2
        
        # Try to contruct a homogeneous sequence of dashes
        # -- for en-dash
        # --- for em-dash
        all_em = hyphens % 3 == 0
        all_en = hyphens % 2 == 0
        while hyphens > 0:
            if all_em:
                state.events.append(
                    Event.leaf(
                        Range(pos, pos+2),
                        InlineLeaf.EM_DASH
                    )
                )
                pos = pos + 3
                hyphens = hyphens - 3
            elif all_en:
                state.events.append(
                    Event.leaf(
                        Range(pos, pos+1),
                        InlineLeaf.EN_DASH
                    )
                )
                pos = pos + 2
                hyphens = hyphens - 2
            elif hyphens >= 3 and (hyphens % 2 != 0 or hyphens > 4): # odd number of dashes
                state.events.append(
                    Event.leaf(
                        Range(pos, pos+2),
                        InlineLeaf.EM_DASH
                    )
                )
                pos = pos + 3
                hyphens = hyphens - 3
            elif hyphens >= 2:
                state.events.append(
                    Event.leaf(
                        Range(pos, pos+1),
                        InlineLeaf.EN_DASH
                    ),
                )
                pos = pos + 2
                hyphens = hyphens - 2
            else:
                state.events.append(Event.leaf(span=Range(pos, pos), kind=InlineLeaf.STR))
                pos = pos + 1
                hyphens = hyphens - 1
        
        return pos
