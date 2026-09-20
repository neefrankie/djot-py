from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    ContainerKind,
    LeafKind,
)
from .matcher import Matcher
from .state import InlineState

class RightParenMatcher(Matcher):

    def __call___(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        # )
        # ![beautiful skyline](clouds.jpg)
        # [read more](https://example.com)
        if not state.destination:
            return None
        
        parens = state.openers['(']
        # TODO: why?
        if parens:
            parens.pop() # clear opener
            state.events.append(Event.leaf(Range(pos, pos), LeafKind.STR))
            return pos+1
        
        openers = state.openers['[']
        opener = openers[-1]
        if not openers:
            return None
    
        if opener.annot != 'explicit_link':
            return None
        
        # we have inline link
        # convert all matches inside destination to str
        # [My link text](http://example.com)
        # opener.subendpos point to (
        state.str_matches((opener.sub_endpos or opener.endpos)+1, pos-1)
        is_image = (state.cursor.is_bang(opener.startpos-1) and
                    not state.cursor.is_backslash(opener.startpos-2))
    
        if is_image:
            # Modify !
            state.replace_event(
                Event.leaf(
                    Range(opener.startpos-1, opener.startpos-1),
                    LeafKind.IMAGE_MARKER,
                ),
                opener.event_index-1
            )
            # modify [
            state.replace_event(
                Event.enter(
                    Range(opener.startpos, opener.endpos),
                    ContainerKind.IMAGE_TEXT,
                ),
                opener.event_index
            )
            # ]
            state.replace_event(
                Event.exit(
                    Range(
                        opener.sub_startpos or opener.startpos,
                        opener.sub_startpos or opener.startpos,
                    ),
                    ContainerKind.IMAGE_TEXT,
                ),
                opener.sub_event_index,
            )
        else:
            # [
            state.replace_event(
                Event.enter(
                    Range(opener.startpos, opener.endpos),
                    ContainerKind.LINK_TEXT,
                ),
                opener.event_index,
            )
            # ]
            state.replace_event(
                Event.exit(
                    Range(
                        opener.sub_startpos or opener.startpos,
                        opener.sub_startpos or opener.startpos,
                    ),
                    ContainerKind.LINK_TEXT,
                ),
                opener.sub_event_index
            )
        # (
        state.replace_event(
            Event.enter(
                Range(
                    opener.sub_endpos or opener.endpos,
                    opener.sub_endpos or opener.endpos,
                ),
                ContainerKind.DESTINATION,
            ),
            opener.sub_event_index+1
        )
        state.events.append(
            Event.exit(Range(pos, pos),ContainerKind.DESTINATION) # current )
        )
        state.destination = False # Flag exiting link.
        state.clear_openers(opener.startpos, pos) # From [ to )
        return pos+1 # after )