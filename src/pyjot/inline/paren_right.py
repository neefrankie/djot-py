from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    InlineLeaf,
    InlineContainer
)
from .matcher import Matcher
from .state import InlineState, OpenerKind

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
            state.events.append(Event.leaf(Range(pos, pos), InlineLeaf.STR))
            return pos+1
        
        openers = state.openers['[']
        opener = openers[-1]
        if not openers:
            return None
    
        if opener.kind != OpenerKind.EXPLICIT_LINK:
            return None
        
        # we have inline link
        # convert all matches inside destination to str
        # [My link text](http://example.com)
        # opener.subendpos point to (
        state.str_matches((opener.sub_endpos or opener.endpos)+1, pos-1)
        is_image = (state.cursor.is_bang(opener.startpos-1) and
                    not state.cursor.is_backslash(opener.startpos-2))
    
        if is_image:
            
            state.replace_event( # Update !
                Event.leaf(
                    Range(opener.startpos-1, opener.startpos-1),
                    InlineLeaf.IMAGE_MARKER,
                ),
                opener.event_index-1
            )
            
            state.replace_event( # update [
                Event.enter(
                    Range(opener.startpos, opener.endpos),
                    InlineContainer.IMAGE_TEXT,
                ),
                opener.event_index
            )
            
            state.replace_event( # Update ]
                Event.exit(
                    Range(
                        opener.sub_startpos or opener.startpos,
                        opener.sub_startpos or opener.startpos,
                    ),
                    InlineContainer.IMAGE_TEXT,
                ),
                opener.sub_event_index,
            )
        else:
            
            state.replace_event( # Update [
                Event.enter(
                    Range(opener.startpos, opener.endpos),
                    InlineContainer.LINK_TEXT,
                ),
                opener.event_index,
            )
            
            state.replace_event( # Upate ]
                Event.exit(
                    Range(
                        opener.sub_startpos or opener.startpos,
                        opener.sub_startpos or opener.startpos,
                    ),
                    InlineContainer.LINK_TEXT,
                ),
                opener.sub_event_index
            )
        
        state.replace_event( # Update (
            Event.enter(
                Range(
                    opener.sub_endpos or opener.endpos,
                    opener.sub_endpos or opener.endpos,
                ),
                InlineContainer.DESTINATION,
            ),
            opener.sub_event_index+1
        )
        state.events.append( # current )
            Event.exit(
                Range(pos, pos),
                InlineContainer.DESTINATION
            ) 
        )
        state.destination = False # Flag exiting link.
        state.clear_openers(opener.startpos, pos) # From [ to )
        return pos+1 # after )