from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional

from ..common import Range
from ..input import InputText
from ..event import (
    Event,
    VerbatimKind,
    InlineLeaf,
)
from ..attributes import AttributeParser
from ..options import Options, Warning

class OpenerKind(Enum):
    REFERENCE_LINK = auto()
    EXPLICIT_LINK = auto()

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

    What happens for [fo[o][bar] or [fo(o]?
    
    """
    event_index: int # Index in Event list.
    startpos: int # point to the first [
    endpos: int
    kind: OpenerKind | None # cannot be determined upon creation. Only clear when sub_startpos is seen
    sub_event_index: int
    sub_startpos: int | None # point to first ]
    sub_endpos: int | None # point to second [

    def is_within(self, startpos: int, endpos: int) -> bool:
        return startpos <= self.startpos and endpos >= endpos

    def is_subrange_within(self, startpos: int, endpos: int) -> bool:
        if self.sub_startpos is None or self.sub_endpos is None:
            return False
        return startpos <= self.sub_startpos and self.sub_endpos <= endpos

@dataclass(slots=True, frozen=True)
class PendingSpan:
    open_event_idx: int
    close_event_idx: int

class InlineState:
    def __init__(self, cursor: InputText, options: Options):
        self.cursor = cursor
        self.options = options

        self.events: List[Event] = []

        # map from opener type to Opener[] in reverse order
        # Each entry is a stack.
        self.openers: Dict[str, List[Opener]] = {}

        # parsing a verbatim span to be ended by N backticks
        self.verbatim_len = 0 # length of verbatim markers.
        self.verbatim_type: VerbatimKind = VerbatimKind.VERBATIM

        self.destination = False # If inside link destination

        self.allow_attributes = True # allow parsing of attributes.
        self.attribute_parser: Optional[AttributeParser] = None
        self.attribute_start: Optional[int] = None # start pos of potential attribute
        self.attribute_spans: Optional[List[Range]] = None # spans we've tried to parse as attributes
        self.pending_span: Optional[PendingSpan] = None

    @property
    def last_event(self) -> Optional[Event]:
        return self.events[-1] if self.events else None

    @property
    def in_verbatim(self) -> bool:
        return self.verbatim_len > 0

    def replace_event(self, event: Event, idx: int):
        if idx < len(self.events):
            self.events[idx] = event

    def push_event(self, event: Event):
        self.events.append(event)

    def trim_last_str_span_trailing(self):
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


    def add_opener(self, name: str, default_event: Event):
        if name not in self.openers:
            self.openers[name] = []

        self.openers[name].append(
            Opener(
                event_index=len(self.events),
                startpos=default_event.span.start,
                endpos=default_event.span.end,
                kind=None, # TODO: Event.action, Event.kind
                sub_event_index=len(self.events),
                sub_startpos=None,
                sub_endpos=None,
            )
        )

        self.events.append(default_event)

    def get_openers(self, name: str) -> List[Opener]:
        return self.openers.get(name, [])

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
                    v[i].sub_startpos = None
                    v[i].sub_endpos = None
                    v[i].kind = None
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
        """Create attribute parser
        
        When a `{` if encountered, and it is not followed by
        inline markup like *, -, etc., it is taken as starting
        attributes.
        """
        self.attribute_parser = AttributeParser(self.cursor)
        self.attribute_start = pos
        self.attribute_spans = []

    def reset_attribute_state(self):
        self.attribute_parser = None
        self.attribute_start = None
        self.attribute_spans = None
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