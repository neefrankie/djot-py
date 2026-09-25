from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, NamedTuple, Optional

from ..common import Range
from ..input import InputText
from ..event import (
    Event,
    VerbatimKind,
    InlineLeaf,
)
from ..options import Options, Warning

class OpenerKind(Enum):
    REFERENCE_LINK = auto()
    EXPLICIT_LINK = auto()

class EventPointer(NamedTuple):
    idx: int # Index in event list
    start: int # start position of this event in source text
    end: int # end position of this event in source text

    def move(self, step: int) -> 'EventPointer':
        return EventPointer(
            idx=self.idx + step,
            start=self.start,
            end=self.end
        )

    @classmethod
    def of_event(cls, event: Event, idx: int) -> 'EventPointer':
        return cls(
            idx=idx,
            start=event.span.start,
            end=event.span.end
        )
    
@dataclass(slots=True)
class Opener:
    """
    Take `[foo][bar]` for example.

    When the first [ is seen, create Opener instance and append an event (name it EA).
    `event_index` is the index of the event we just added.
    `startpos` and `endpos` is the same as EA's span.
    `sub_event_index` also points to the index of EventA.
    `annot` is None.
    `sub_startpos` is None
    `sub_endpos` is None
    When the first ] is seen, we get the Opener on from the top of stack.
    We then check the char after ], it is another [.
    Now we could set `annot = reference_link`.
    Create a new event for `]` as str. Name it EventB.
    `sub_event_index` points to EventB.
    Since we already know there's another `[` following `]`, add a new event
    for the second `[` called EeventC.
    `sub_startpos` is set to the position of `]`.
    `sub_endpos` is set to the position of second `[`.
    Move cursor to `b`.
    If we have created any openers between `[` and `]` (exclusive), delete them.

    [             startpos / endpos, Event A, event_index
    My link text
    ]             sub_startpos, Event B, sub_event_index
    [             sub_endpos, Enter reference
    foobar
    ]             Exit reference
    
    an opener cotainers such data:
    - Index of an event in events list
    - The event's span
    So we could reorganize into a new data struct:
    
    EventPointer:
        index: int
        span: Range

    Then opener could be reorganized into:
    Opener:
        text_opener: EventPointer # exists upon creation
        text_closer: EventPointer | None = None # known when we see ]
        dest_or_label_opener: EventPointer | None = None
    """
    event_index: int # Index in Event list.
    startpos: int # point to the first [
    endpos: int
    kind: OpenerKind | None # cannot be determined upon creation. Only clear when sub_startpos is seen
    sub_event_index: int # points to the first closing ]
    sub_startpos: int | None # point to first closing ]
    sub_endpos: int | None # point to second [

    def is_within(self, startpos: int, endpos: int) -> bool:
        return startpos <= self.startpos and endpos >= endpos

    def is_subrange_within(self, startpos: int, endpos: int) -> bool:
        if self.sub_startpos is None or self.sub_endpos is None:
            return False
        return startpos <= self.sub_startpos and self.sub_endpos <= endpos

    def set_first_closer(self, pointer: EventPointer):
        self.sub_event_index = pointer.idx
        self.sub_startpos = pointer.start

    def set_second_opener(self, pointer: EventPointer, kind: OpenerKind):
        self.sub_endpos = pointer.start
        self.kind = kind

    @classmethod
    def new(cls, event: Event, evt_idx: int) -> 'Opener':
        return Opener(
            event_index=evt_idx,
            startpos=event.span.start,
            endpos=event.span.end,
            kind=None,
            sub_event_index=evt_idx,
            sub_startpos=None,
            sub_endpos=None,
        )



@dataclass(slots=True)
class OpenerV2:
    """Remember each phase when parsing ambiguous delimiters

    In my opinion there are two groups of paired delimiters in Djot/Markdown:
    `{* bold *}` and `[Text][foo]`. They roughly correspond to 
    primivate value vs composite value in a programming langauge.

    BTW, I was told by Gemini that John MacFarlane proposed simiar ideas.
    I'm not sure what he called this pattern.

    It takes 3 phases to figure out the exact meaning of a composite value.

    Phase 1.
    When you see opening bracket, is it an reference link? Inline link? Span?
    We are not sure. So treat it as plain str and remember its position in event list.
    It happens in LeftBracketMatcher.

    Phase 2.
    When you the first ], you can peek the char following ].
    Is it paren, or another opening bracket, or opening brace?
    Now we can determine the the purpose the the first pair of `[]`.
    But we still cannot make sure whether it is valid or not.
    It happens in RightBracketMatcher.

    Phase 3.
    When you see the the final ] or ), we are sure it is realy a reference link,
    or explicit link, of attributes following a Span.
    Now we can use the record save here to modify the events already generated.
    It happens in RightBracketMatcher and LeftParenMatcher.
    """
    text_opener: EventPointer
    text_closer: Optional[EventPointer] = None
    target_opener: Optional[EventPointer] = None
    kind: Optional[OpenerKind] = None

    def set_first_closer(self, pointer: EventPointer):
        self.text_closer = pointer

    def set_second_opener(self, pointer: EventPointer, kind: OpenerKind):
        self.target_opener = pointer
        self.kind = kind

    def clear_multi_stage(self):
        self.text_closer = None
        self.target_opener = None
        self.kind = None

    @property
    def startpos(self) -> int:
        return self.text_opener.start

    @property
    def endpos(self) -> int:
        return self.text_opener.end

    @property
    def event_index(self) -> int:
        return self.text_opener.idx

    @property
    def sub_event_index(self) -> int:
        if self.text_closer:
            return self.text_closer.idx

        return self.text_opener.idx

    @property
    def sub_startpos(self) -> Optional[int]:
        if self.text_closer:
            return self.text_closer.start

        return None
    
    @property
    def sub_endpos(self) -> Optional[int]:
        if self.target_opener:
            return self.target_opener.start

        return None

    def move(self, step: int):
        self.text_opener = self.text_opener.move(step)

        if self.text_closer:
            self.text_closer = self.text_closer.move(step)

        if self.target_opener:
            self.target_opener = self.target_opener.move(step)

    def is_within(self, startpos: int, endpos: int) -> bool:
            return startpos <= self.startpos and endpos >= endpos
    
    def is_subrange_within(self, startpos: int, endpos: int) -> bool:
        if self.sub_startpos is None or self.sub_endpos is None:
            return False
        return startpos <= self.sub_startpos and self.sub_endpos <= endpos

    @classmethod
    def new(cls, event: Event, evt_idx: int) -> 'OpenerV2':
        return cls(
            text_opener=EventPointer(
                idx=evt_idx,
                start=event.span.start,
                end=event.span.end,
            ),
            text_closer=None,
            target_opener=None,
            kind=None,
        )

@dataclass(slots=True, frozen=True)
class PendingSpan:
    """The position of possible Span event
    
    When the bracket part of [text]{.class} is seen, you cannot determine
    if it is a span element until the following attribute is parsed.
    If attribute parsing fails, the span should degenerate to plain text.
    """
    open_event_idx: int # Event index for [
    close_event_idx: int # Event index for ]

class InlineState:
    def __init__(self, cursor: InputText, options: Options):
        self.cursor = cursor
        self.options = options

        self.events: List[Event] = []

        # map from opener type to Opener[] in reverse order
        self.openers: Dict[str, List[OpenerV2]] = {}

        # parsing a verbatim span to be ended by N backticks
        self.verbatim_len = 0 # length of verbatim markers.
        self.verbatim_type: VerbatimKind = VerbatimKind.VERBATIM

        self.destination: bool = False # If inside link destination

        self.allow_attributes = True # allow parsing of attributes.

        self.in_attribute: bool = False
        # Initiated in when a } is seen followed by a {.
        self.pending_span: Optional[PendingSpan] = None 

    @property
    def last_event(self) -> Optional[Event]:
        return self.events[-1] if self.events else None

    @property
    def event_len(self) -> int:
        return len(self.events)

    @property
    def in_verbatim(self) -> bool:
        return self.verbatim_len > 0

    def set_verbatim(self, pos: int, endpos: int, typ: VerbatimKind):
        self.verbatim_type = typ
        self.verbatim_len = endpos - pos + 1

    def replace_event(self, event: Event, idx: int):
        if idx < len(self.events):
            self.events[idx] = event

    def extend_events(self, events: List[Event]):
        self.events.extend(events)

    def pop_events_upto(self, starpos: int) -> int:
        i = len(self.events) - 1
        while i > 0 and self.events[i].span.start > starpos:
            self.events.pop()
            i -= 1

        return i

    def push_event(self, event: Event):
        self.events.append(event)

    def trim_last_event_if_str(self):
        if not self.events:
            return

        last_match = self.events[-1]
        if not last_match.is_str:
            return

        ep = self.cursor.find_trailing_space(last_match.span)
        if ep < last_match.span.start:
            self.events.pop() # space only
        else:
            last_match.span.shrink_end(ep) # change end position to first non-space char.


    def is_cross_link_boudnary(self, opener_startpos: int) -> bool:
        """Check if opener crossed link boundary.

        If a delimiter is opened before a link, but a closing delimiter
        is found inside link destination, this closing delimiter
        should taken as plain text.

        For example, `_here [My link text](http://example_site.org)`.
        When the underscore in link destination is found, we check
        that there's an opener appeared early than [, so we can not close it.
        The second underscore is treated as plain text.
        """

        if not self.destination:
            return False

        link_openers = self.openers.get('[', [])
        if not link_openers:
            return False

        last_link_opener = link_openers[-1]
        # If the opener starts early than link's '[' symbol
        return opener_startpos < last_link_opener.startpos

    def add_candidate_event(self, event: Event) -> EventPointer:
        ep = EventPointer(
            idx=len(self.events),
            start=event.span.start,
            end=event.span.end
        )
        self.events.append(event)
        return ep

    def add_image_marker(self, opener: OpenerV2):
        """Move ! from previous event to the one pointed by opener.

        For example, `hello ![image](image.png)` might generated
        Event(hello !), Event([), Event(image), etc..
        When we found Event([) actually indicates image, we need to
        transfer ! from previous event to Event(![).
        
        """
        prev_idx = opener.text_opener.idx - 1
        prev_event = self.events[prev_idx]

        img_event = Event.leaf(
            span=Range(opener.startpos - 1, opener.startpos - 1),
            kind=InlineLeaf.IMAGE_MARKER,
        )
        
        if prev_event.is_str and prev_event.startpos < opener.startpos - 1:
            # '!' is grouped with preceding text in a single str match.
            # Truncate the str to end before '!' and insert image_marker.
            # For example, in 'hello ![image](image.png)', 
            # opener.startpos is  7, pointing to '[' while previous str
            # event spans from 0 to 6. We need to truncate the str to 5
            # and insert ! as a separate event.
            prev_event.shrink_end(opener.startpos - 2)
            
            self.events.insert(opener.event_index, img_event)
            # Adjust indices since we inserted a new element
            opener.move(1)
            return

        # '!' is alone in its str match, replace it directly
        self.replace_event(
            img_event,
            prev_idx
        )
    
    def add_opener(self, name: str, default_event: Event):
        if name not in self.openers:
            self.openers[name] = []

        ep = self.add_candidate_event(default_event)

        opener = OpenerV2.new(default_event, ep.idx)
        self.openers[name].append(opener)

        return opener


    def get_openers(self, name: str) -> List[OpenerV2]:
        return self.openers.get(name, [])

    def reset_openers(self, name: str):
        self.openers[name] = []

    def clear_openers(self, startpos: int, endpos: int):
        """
        Delete opener created inside an opener.
        """
        for v in self.openers.values():
            i = len(v) - 1 # last index
            while i >= 0: # last opener
                opener = v[i]
                # If opener falls into the range of startpos to endpos
                if opener.is_within(startpos, endpos):
                    del v[i]
                elif opener.is_subrange_within(startpos, endpos):
                    # If opener substartps to subendpos falls into startpos and endpos
                    v[i].clear_multi_stage()
                else:
                    break

                i -= 1

    def str_matches(self, startpos: int, endpos: int):
        i = len(self.events) - 1
        # Find the last event appeared before startpos
        while i > 0 and self.events[i].span.start >= startpos:
            i -= 1

        # Find the last event appeared just after startpos
        if self.events[i].span.start < startpos:
            i += 1

        # Change events between startpos and endpos to STR. Why?
        while i < len(self.events) and self.events[i].span.end <= endpos:
            m = self.events[i]
            if m.kind != InlineLeaf.ESCAPE and m.kind != InlineLeaf.STR:
                m.demote_to_str()

            i += 1

    def init_attribute_parser(self, pos: int):
        self.in_attribute = True

    def reset_attribute_state(self):
        self.in_attribute = False

    def set_pending_span(self, opener: OpenerV2):
        self.pending_span = PendingSpan(
            open_event_idx=opener.text_opener.idx,
            close_event_idx=len(self.events)-1
        )

    def demote_span_to_str(self):
        if self.pending_span is None:
            return

        self.events[self.pending_span.open_event_idx].demote_to_str()
        self.events[self.pending_span.close_event_idx].demote_to_str()

        self.pending_span = None

    def get_matches(self) -> List[Event]:
        """Get parsed events.
        
        Remove trailing softbreak and any spaces.

        If verbatim is not closed, it will be closed.
        """
        # if self.attribute_parser:
        #     self.reparse_attributes()
        if not self.events:
            return []

        # remove trailing softbreak and any spaces
        if self.events[-1].is_soft_break:
            self.events.pop() # removed last one
            if not self.events:
                return []

            last_event = self.events[-1]
            
            if last_event.is_str and self.cursor.is_space(last_event.span.end):

                last_event.span.end = self.cursor.find_trailing_space(last_event.span)

                if last_event.span.end < last_event.span.start:
                    self.events.pop()

        if not self.events:
            return []
        
        if self.verbatim_len > 0:
            # unclosed verbatim
            last = self.events[-1]
            self.options.warn(Warning(
                message='Unclosed verbatim',
                pos=last.span.end,
            ))
            self.events.append(
                Event.exit(
                    span=Range(
                        last.span.end,
                        last.span.end,
                    ),
                    kind=self.verbatim_type,
                )
            )

        return self.events