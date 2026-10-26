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

class LeftBraceMatcher(Matcher):
    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        # Braced delimiter
        # { followed by any _*~^+='"-
        # {_italic_}
        # {*bold*}
        # H~2~O
        # 20^th^
        # {+insert+}
        # {=heighlight=}
        # {''}
        # {""}
        # {- -}
        # Implicit precedence: delimiter > attribute > plain text
        # TODO: combine left brace and delimiter into a single opening token.
        if state.cursor.is_delimiter(pos+1):  # if next char is one of delimiters
            state.push_event( # current { is open marker
                Event.leaf(
                    Range(pos, pos), 
                    InlineLeaf.OPEN_MARKER
                )
            )
            return pos+1

        # Prepare to parse attributes from {
        # NOTE: escaped { won't go here. It is handled by backslash matcher.
        if state.allow_attributes:
            state.enter_attribute(pos)
            return pos

        state.push_event(Event.str(pos, pos))
        return pos + 1