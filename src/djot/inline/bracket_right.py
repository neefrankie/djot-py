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
from .state import (
    InlineState,
    OpenerKind,
    OpenerV2,
)

class RightBracketMatcher(Matcher):

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        """Extract information from a right bracket.

        The general idea is, when we see the first [, we have no idea what will follow.
        When we see the first ], we could determined the purpose of the first pair of brackets.
        When we see ] the second time, we are closing the reference link

        This function plays two roles:

        - If we are reaching the first closing bracket, try to exract information as to how the bracket is used;
        - If we are reaching the second closing bracket, modify placehoder events.
        """
        openers = state.get_openers('[')
        if not openers:
            return None
        
        opener = openers[-1]

        is_note_ref = state.cursor.is_hat(opener.text_opener.start + 1) # [^

        # [^foo]
        # pos -> ]
        # opener.text_opener.start -> [
        if is_note_ref:
            return self._commit_note_reference(state, opener, pos)

        # [My link text][foo bar]
        # ![picture of a cat][cat]
        # We have reached the second close bracket, that is,
        # the end of a reference link.
        # Now everything is clear and we can backtrace to modify
        # placeholder events.
        # Found a reference link
        # Here we are handling the third phase of Opener
        if opener.kind == OpenerKind.REFERENCE_LINK:
           return self._commit_reference(state, opener, pos)

        # The following logic tries to extract information from 
        # the first pair of brackets.
        # Next char is second left [ as in [My link text][foo bar]
        # Here we are handling the second phase of Opener
        if pos+1 <= endpos and state.cursor.is_left_bracket(pos+1):
            return self._prepare_reference(state, opener, pos)
            
        # Inline link or inline image.
        # Here we are handling the second phase of Opener, again.
        if pos+1 <= endpos and state.cursor.is_left_paren(pos+1):
            return self._prepare_explicit(state, opener, pos)
            
        # Attributes.
        # [a span]{.some-class #some-id some-key="some val"
        # Why special treatment of Span?
        # Because Span usage is ambiguous.
        # For othher elements like _epmh_{.dark}, the meaning of
        # underscore is clear regardless of attributes exist or not.
        # But Span is only meaningful when followed by attributes.
        # Here we are handling the second phase of Opener, again.
        if pos+1 <= endpos and state.cursor.is_left_brace(pos+1):
            return self._prepare_span(state, opener, pos)
        
        return None

    def _commit_note_reference(self, state: InlineState, opener: OpenerV2, pos: int) -> int:
        i = state.pop_events_upto(opener.startpos)
        state.clear_openers(opener.startpos, pos)
        state.events[i].kind = InlineLeaf.FOOTNOTE_REF
        state.events[i].span.end = pos

        return pos+1

    def _commit_reference(self, state: InlineState, opener: OpenerV2, pos: int) -> int:
        # convert all matches inside reference label to str
        state.str_matches((opener.sub_endpos or opener.endpos)+1, pos-1)

        # Backtracing to see if this is image.
        # Image is `![` but not `\![`.
        is_image = state.cursor.is_bang(opener.startpos-1) and  not state.cursor.is_backslash(opener.startpos-2)

        if is_image:
            self._commit_image(state, opener)
        else:
            self._commit_link(state, opener)
        
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
        # Remove all openers falls into the range of the whole reference link.
        state.clear_openers(opener.startpos, pos)
        return pos+1 # after ]

    def _commit_image(self, state: InlineState, opener: OpenerV2):
        # ![picture of a cat][cat.jpg]
        # Modify events aleady emitted for `!`, `[` and `]`.
        state.add_image_marker(opener)
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

    def _commit_link(self, state: InlineState, opener: OpenerV2):
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

    def _prepare_reference(self, state: InlineState, opener: OpenerV2, pos: int):

        # In this example [Text][foo],
        # pos is pointing to the first right bracket now.
        # This delimiter does not give much information at this step.
        # We could only deduce it might be a reference link from the next char `[`.
        # So the two char `][` gives different information.
        # `]` only tells you "OK, I can close properly". Nothing more.
        # It the following opening bracket `[` that tells this might be
        # a reference link, but it's not sure yet since the second closing
        # bracket is yet to merge.
        
        # In djot.js, the state change is mixed here.
        # We separate it into two clear steps for each delimiter.
        # Here's the event generated from ], and we refresh opener
        # based on this event's index and spanned range.
        close_ep = state.add_candidate_event(
            Event.leaf( # ]
                Range(pos, pos),
                InlineLeaf.STR
            )
        )
        opener.set_first_closer(close_ep)


        # The second step derives more information from the second `[`.
        open_ep = state.add_candidate_event(
            Event.leaf(
                Range(pos+1, pos+1),
                InlineLeaf.STR,
            )
        )
        opener.set_second_opener(open_ep, OpenerKind.REFERENCE_LINK)

        # remove any openers between [ and ]
        state.clear_openers(opener.startpos+1, pos-1)
        return pos+2 # after ][

    def _prepare_explicit(self, state: InlineState, opener: OpenerV2, pos: int):
        
        state.reset_openers('(') # clear ( openers. Why?

        close_ep = state.add_candidate_event(
            Event.leaf( # ]
                Range(pos, pos),
                InlineLeaf.STR
            )
        )
        opener.set_first_closer(close_ep)


        # The second step derives more information from the `(`.
        open_ep = state.add_candidate_event(
            Event.leaf(
                Range(pos+1, pos+1),
                InlineLeaf.STR,
            )
        )
        opener.set_second_opener(open_ep, OpenerKind.EXPLICIT_LINK)

        state.destination = True

        # remove any openers inside [ and ]
        state.clear_openers(opener.startpos + 1, pos - 1)
        return pos + 2 # after ](

    def _prepare_span(self, state: InlineState, opener: OpenerV2, pos: int):
        # assume this is attributes, bracketed span.
        # [a span]{.some-class #some-id some-key="some val"}
        state.replace_event( # [ is opening span
            Event.enter(
                Range(opener.startpos, opener.endpos),
                InlineContainer.SPAN
            ),
            opener.event_index
        )

        state.push_event( # ]
            Event.exit(
                Range(pos, pos),
                InlineContainer.SPAN
            )
        )

        state.set_pending_span(opener)

        # remove any openers between [ and ]
        state.clear_openers(opener.startpos, pos)
        return pos+1 # Leave { for attribute parser.