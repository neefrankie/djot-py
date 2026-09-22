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
        if state.cursor.find_delimiter(pos+1, endpos):  # if next char is one of delimiters
            state.events.append( # current { is open marker
                Event.leaf(
                    Range(pos, pos), 
                    InlineLeaf.OPEN_MARKER
                )
            )
            return pos+1
        elif state.allow_attributes:
            # Prepar to parse attributes from {
            # Why the flag allow_attributes?
            # When attribute parsing failed, you could disable allow_attributes
            # so that the parse could re-parse it as plain text.
            # TODO: this might not be needed if we could simply attributes
            # in Djot specification.
            state.init_attribute_parser(pos)
            return pos 
        else:
            state.events.append(
                Event.leaf(
                    Range(pos, pos),
                    InlineLeaf.STR
                )
            ) # literal {
            return pos+1