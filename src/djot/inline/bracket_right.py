from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    InlineLeaf,
    InlineContainer,
)
from .matcher import Matcher
from .state import InlineState, OpenerKind, PendingSpan

class RightBracketMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        """Extract information from a right bracket.

        The general idea is, when we see the first [, we have no idea what will follow.
        When we see the first ], we could determined the purpose of the first pair of brackets.
        When we see ] the second time, we are closing the reference link

        This function plays two roles:

        - If we are reaching the first closing bracket, try to exract information as to how the bracket is used;
        - If we are reaching the second closing bracket, modify placehoder events.

        [             startpos / endpos, Event A, event_index
        My link text
        ]             sub_startpos, Event B, sub_event_index
        [             sub_endpos, Enter reference
        foobar
        ]             Exit reference
        """
        openers = state.openers['[']
        if not openers:
            return None
        
        opener = openers[-1]

        # [My link text][foo bar]
        # ![picture of a cat][cat]
        # We have reached the second close bracket, that is,
        # the end of a reference link.
        # Now everything is clear and we can backtrace to modify
        # placeholder events.
        if opener.kind == OpenerKind.REFERENCE_LINK:
            # Found a reference link
            # convert all matches inside reference to str
            # Anything between opener and pos should be treated as plain text.
            # We are handling content inside second pair of brackets
            state.str_matches((opener.sub_endpos or opener.endpos)+1, pos-1)

            # Backraracing to see if this is image.
            # Image is `![` but not `\![`.
            is_image = state.cursor.is_bang(opener.startpos-1) and  not state.cursor.is_backslash(opener.startpos-2)

            if is_image:
                # TODO: addImageMarker(opener)
                # ![picture of a cat][cat.jpg]
                # Modify events aleady emitted for `!`, `[` and `]`.
                state.replace_event( # Update ! event
                    Event.leaf(
                        Range(opener.startpos-1, opener.startpos-1), # !
                        InlineLeaf.IMAGE_MARKER
                    ), 
                    opener.event_index-1 # the index before opener
                )
                state.replace_event( # Update [ event
                    Event.enter(
                        Range(opener.startpos, opener.endpos),
                        InlineContainer.IMAGE_TEXT
                    ),
                    opener.event_index
                )
                # ][ is the sub-range.
                state.replace_event(
                    Event.exit( # first ]
                        Range(
                            opener.sub_startpos or opener.startpos,
                            opener.sub_startpos or opener.startpos
                        ),
                        InlineContainer.IMAGE_TEXT,
                    ),
                    opener.sub_event_index
                )
            else:
                # [My link text][http://example.com]
                # Modify events for first pair of `[` and `]`
                state.replace_event(
                    Event.enter( # [
                        Range(opener.startpos, opener.endpos),
                        InlineContainer.LINK_TEXT,
                    ),
                    opener.event_index,
                )
                state.replace_event(
                    Event.exit( # ]
                        Range(
                            opener.sub_startpos or opener.startpos,
                            opener.sub_startpos or opener.startpos
                        ),
                        InlineContainer.LINK_TEXT
                    ),
                    opener.sub_event_index,
                )
            
            # Modify second [
            state.replace_event(
                Event.enter( # second [
                    Range(
                        opener.sub_endpos or opener.endpos,
                        opener.sub_endpos or opener.endpos
                    ),
                    InlineContainer.REFERENCE,
                ),
                opener.sub_event_index+1
            )
            # Current char is the second ]
            state.events.append(
                Event.exit(
                    Range(pos,pos),
                    InlineContainer.REFERENCE
                )
            )
            # Remove all openers for current reference link.
            state.clear_openers(opener.startpos, pos)
            return pos+1 # after ]

        # The following logic tries to extract information from 
        # the first pair of brackets.
        # Next char is second left [ as in [My link text][foo bar]
        if pos+1 <= endpos and state.cursor.is_left_bracket(pos+1):
            
            opener.kind = OpenerKind.REFERENCE_LINK

            # Add event for current char ].
            # TODO: is InlineLeaf.STR a placeholder?
            state.events.append(
                Event.leaf(
                    Range(pos, pos),
                    InlineLeaf.STR
                )
            )

            # The event we just created
            opener.sub_event_index = len(state.events) - 1

            # Add event for next char [
            state.events.append(
                Event.leaf(Range(pos+1, pos+1), InlineLeaf.STR)
            )

            # Current char [ is a sub start.
            opener.sub_startpos = pos
            # Next char ] is a sub end
            opener.sub_endpos = pos+1

            # remove any openers between [ and ]
            state.clear_openers(opener.startpos+1, pos-1)
            return pos+2 # after ][

        # Inline link or inline image.
        if pos+1 <= endpos and state.cursor.is_left_paren(pos+1):
            
            state.openers['('] = [] # clear ( openers. Why?
            opener.kind = OpenerKind.EXPLICIT_LINK

            state.events.append( # ]
                Event.leaf(
                    Range(pos, pos),
                    InlineLeaf.STR
                )
            )
            # The event just created.
            opener.sub_event_index = len(state.events) - 1

            state.events.append( # (
                Event.leaf(
                    Range(pos+1, pos+1),
                    InlineLeaf.STR
                )
            )
            # Position for ](
            opener.sub_startpos = pos
            opener.sub_endpos = pos + 1

            self.destination = True

            # remove any openers inside [ and ]
            state.clear_openers(opener.startpos + 1, pos - 1)
            return pos + 2 # after ](

        # Attributes.
        # [a span]{.some-class #some-id some-key="some val"
        # Why special treatment of Span?
        # Because Span usage is ambiguous.
        # For othher elements like _epmh_{.dark}, the meaning of
        # underscore is clear regardless of attributes exist or not.
        # But Span is only meaningful when followed by attributes.
        if pos+1 <= endpos and state.cursor.is_left_brace(pos+1):
            # assume this is attributes, bracketed span.
            # [a span]{.some-class #some-id some-key="some val"}
            state.replace_event( # [ is opening span
                Event.enter(
                    Range(opener.startpos, opener.endpos),
                    InlineContainer.SPAN
                ),
                opener.event_index
            )

            state.events.append( # ]
                Event.exit(
                    Range(pos, pos),
                    InlineContainer.SPAN
                )
            )

            if state.allow_attributes:
                state.pending_span = PendingSpan(
                    open_event_idx=opener.event_index,
                    close_event_idx=len(state.events)-1
                )

            # remove any openers between [ and ]
            state.clear_openers(opener.startpos, pos)
            return pos+1 # Leave { for attribute parser.
        
        return None