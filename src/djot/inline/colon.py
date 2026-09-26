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

class ColonMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        """Symbol
    
        Surrounding a word with `:` signs creates a "symbol," which by
        default is just rendered literally but may be treated specially
        by a filter.

        My reaction is :+1: :smiley:.

        Implicit precedence: symbol > plain text
        """
        
        m = state.cursor.find_symbol(pos, endpos)
        if m:
            state.events.append(
                Event.leaf(
                    Range(m.start, m.end),
                    InlineLeaf.SYMBOL
                )
            ) 
            return m.end+1 # after closing :
        else:
            state.events.append(
                Event.leaf(
                    Range(pos, pos),
                    InlineLeaf.STR
                )
            ) # : is plain text.
            return pos+1