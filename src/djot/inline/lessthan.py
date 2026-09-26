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
        m = state.cursor.find_autolink(pos, endpos)
        if m is None:
            return None

        starturl = m.start
        endurl = m.end
        url = m.captures[0]

        if is_email(url):
            state.push_event(
                Event.enter(
                    Range(starturl, starturl),
                    InlineContainer.EMAIL
                )
            ) # <
            state.push_event(
                Event.leaf(
                    Range(starturl+1, endurl-1),
                    InlineLeaf.STR
                )
            ) # email
            state.push_event(
                Event.exit(
                    Range(endurl, endurl), 
                    InlineContainer.EMAIL
                )
            ) # >
            return endurl+1 # after  >
        
        if is_url(url):
            state.push_event(
                Event.enter(
                    Range(starturl, starturl),
                    InlineContainer.URL
                )
            ) # <
            state.push_event(
                Event.leaf(
                    Range(starturl+1, endurl-1),
                    InlineLeaf.STR
                )
            ) # url
            state.push_event(
                Event.exit(
                    Range(endurl, endurl),
                    InlineContainer.URL
                )
            ) # >
            return endurl+1 # after >
        
        return None