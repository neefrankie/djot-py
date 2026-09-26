from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    InlineContainer
)
from .matcher import Matcher
from .state import InlineState, OpenerKind, OpenerV2

class RightParenMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        # )
        # ![beautiful skyline](clouds.jpg)
        # [read more](https://example.com)
        if not state.destination:
            return None
        # If we are in link mode, there should not be a valid
        # opener record for opening paren. If it exists, it should
        # be a plain text.
        # RightBracketMatcher already consumed the opening paren
        # without geerating a new opener for '('.
        parens = state.get_openers('(')
        
        if parens:
            parens.pop() # clear opener
            state.push_event(
                Event.str(pos, pos)
            )
            return pos+1
        
        openers = state.get_openers('[')
        
        if not openers:
            return None

        opener = openers[-1]
    
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
            self._commit_image(state, opener)
        else:
            self._commit_link(state, opener)
        
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

    def _commit_image(self, state: InlineState, opener: OpenerV2):
            state.add_image_marker(opener)
            
            state.replace_event( # Opening [
                Event.enter(
                    Range(opener.startpos, opener.endpos),
                    InlineContainer.IMAGE_TEXT,
                ),
                opener.event_index
            )
            
            state.replace_event( # Closing ]
                Event.exit(
                    Range(
                        opener.sub_startpos or opener.startpos,
                        opener.sub_startpos or opener.startpos,
                    ),
                    InlineContainer.IMAGE_TEXT,
                ),
                opener.sub_event_index,
            )

    def _commit_link(self, state: InlineState, opener: OpenerV2):
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