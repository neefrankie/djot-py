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

class LeftBracketMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        """Role of bracket

        | Role               | Example                              |
        | ------------------ | ------------------------------------ |
        | Inline link        | `[My link text](http://example.com)` |
        | Reference link     | `[My link text][foo bar]`            |
        | Inline Image       | `![picuture of a cat](cat.jpg)`      |
        | Reference Image    | `![picture of a cat][cat]`           |
        | Reference link     | `[foo bar]: http://example.com`      |
        | Footnote reference | `[^foo]`                             |
        | Footnote           | `[^foo]: This is a note`             |
        | Span               | `[read the manual]{.big .red}`       |
        """
        
        # We know little about this bracket.
        # More information is deferred to right bracket.
        state.add_opener(
            '[',
            Event.leaf(
                Range(pos, pos),
                InlineLeaf.STR
            )
        )
        return pos+1