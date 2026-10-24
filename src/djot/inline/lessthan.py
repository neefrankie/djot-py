import re
from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    InlineContainer,
    InlineLeaf,
)
from .matcher import Matcher
from .state import InlineState

_RE_EMAIL = re.compile(r'[^:]@')
_RE_URL = re.compile(r'[a-zA-Z]:/')

def is_email(s: str) -> bool:
    return _RE_EMAIL.search(s) is not None

def is_url(s: str) -> bool:
    return _RE_URL.search(s) is not None

class LessthanMatcher(Matcher):
    """
    A URL or email address that is enclosed in `<...>`
    will hyperlinked. The content between pointy braces
    is treated literally (backbalsh-esacpes may not be used)

    ```
    <https://pandoc.org/lua-filters>
    <me@example.com>
    ```

    The URL or email address may not contain a newline.
    """

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        token = state.cursor.find_autolink(pos, endpos)
        if token is None:
            return None

        if is_email(token.url):
            state.push_event(
                Event.enter(
                    Range(token.start, token.start),
                    InlineContainer.EMAIL
                )
            ) # <
            state.push_event(
                Event.leaf(
                    Range(token.start+1, token.end-1),
                    InlineLeaf.STR
                )
            ) # email
            state.push_event(
                Event.exit(
                    Range(token.end, token.end), 
                    InlineContainer.EMAIL
                )
            ) # >
            return token.end+1 # after  >
        
        if is_url(token.url):
            state.push_event(
                Event.enter(
                    Range(token.start, token.start),
                    InlineContainer.URL
                )
            ) # <
            state.push_event(
                Event.leaf(
                    Range(token.start+1, token.end-1),
                    InlineLeaf.STR
                )
            ) # url
            state.push_event(
                Event.exit(
                    Range(token.end, token.end),
                    InlineContainer.URL
                )
            ) # >
            return token.end+1 # after >
        
        return None