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
        if state.cursor.is_delimiter(pos+1):  # if next char is one of delimiters
            state.events.append( # current { is open marker
                Event.leaf(
                    Range(pos, pos), 
                    InlineLeaf.OPEN_MARKER
                )
            )
            return pos+1

        # Attributes
        # Prepar to parse attributes from {
        # In djot.js there is a flag allow_attributes.
        # When attribute parsing failed, you could disable allow_attributes
        # so that the parse could re-parse it as plain text.
        # Since we do not permi newline in attribute, there is no backtracing.
        # So always treat { as attribute start
        # NOTE: escaped { won't go here. It is handled by backslash matcher.
        state.init_attribute_parser(pos)
        return pos