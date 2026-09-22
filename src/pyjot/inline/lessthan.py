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

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        m = state.cursor.find_autolink(pos, endpos)
        if m is None:
            return None

        starturl = m.start
        endurl = m.end
        url = m.captures[0]
        if is_email(url):
            state.events.append(Event.enter(Range(starturl, starturl), InlineContainer.EMAIL)) # <
            state.events.append(Event.leaf(Range(starturl+1, endurl-1), InlineLeaf.STR)) # email
            state.events.append(Event.exit(Range(endurl, endurl), InlineContainer.EMAIL)) # >
            return endurl+1 # after  >
        elif is_url(url):
            state.events.append(Event.enter(Range(starturl, starturl), InlineContainer.URL)) # <
            state.events.append(Event.leaf(Range(starturl+1, endurl-1), InlineLeaf.STR)) # url
            state.events.append(Event.exit(Range(endurl, endurl), InlineContainer.URL)) # >
            return endurl+1 # after >
        
        return None