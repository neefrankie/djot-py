from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    InlineContainer,
    InlineLeaf,
)
from ..input import InputText
from .matcher import Matcher
from .state import InlineState, OpenerV2

class DelimiterCap(IntFlag):
    """Position of delimiter relative to space
    
    Correspond to can_open and can_close in djot.js implementation
    """
    NONE = auto() # False, Fase. ` * `
    CAN_OPEN = auto()        # True,  False ` *A`
    CAN_CLOSE = auto()       # False, True  `A* `
    BOTH = CAN_OPEN | CAN_CLOSE # True, True `A*B`

class MarkerStyle(Enum):
    NONE = auto() # implicit like `*`, delimited by surrounding spaces
    OPEN = auto() # explicit opening like `{_`
    CLOSE = auto() # explicit closing like `_}`

    @property
    def is_explicit(self) -> bool:
        return self != MarkerStyle.NONE

@dataclass(slots=True, frozen=True)
class MatchContext:
    """MatchContext stores a delimiter's surrouding information"""
    delimiter_cap: DelimiterCap
    token_start: int # position of opening delimiter. Will `token_start` be more clear?
    token_end: int
    marker_style: MarkerStyle = MarkerStyle.NONE # None if no brace.

    @property
    def can_open(self) -> bool:
        return DelimiterCap.CAN_OPEN in self.delimiter_cap

    @property
    def can_close(self) -> bool:
        return DelimiterCap.CAN_CLOSE in self.delimiter_cap

    @property
    def has_open_marker(self) -> bool:
        return self.marker_style == MarkerStyle.OPEN

    @property
    def has_close_marker(self) -> bool:
        return self.marker_style == MarkerStyle.CLOSE

def opening_brace_context(
    current_pos: int,
    last_event: Optional[Event],
) -> Optional[MatchContext]:
    if not last_event:
        return None

    if not last_event.is_open_marker:
        return None

    # has open marker
    return MatchContext(
        delimiter_cap=DelimiterCap.CAN_OPEN,
        token_start=current_pos-1,
        token_end=current_pos,
        marker_style=MarkerStyle.OPEN,
    )

def closing_brace_context(
    cursor: InputText,
    current_pos: int,
    endpos: int,
) -> Optional[MatchContext]:
    if current_pos >= endpos:
        return None

    # no close marker
    if not cursor.is_right_brace(current_pos+1):
        return None

    # has close marker
    return MatchContext(
        delimiter_cap=DelimiterCap.CAN_CLOSE,
        token_start=current_pos,
        token_end=current_pos+1,
        marker_style=MarkerStyle.CLOSE,
    )

def determine_brace_context(
    cursor: InputText,
    current_pos: int,
    endpos: int,
    last_event: Optional[Event], # to determine opening brace.
) -> Optional[MatchContext]:
    opener_ctx = opening_brace_context(current_pos, last_event)

    if opener_ctx:
        return opener_ctx

    return closing_brace_context(cursor, current_pos, endpos)

def determine_bare_context(
    cursor: InputText,
    current_pos: int,
    can_open: bool,
) -> MatchContext:
    cap = DelimiterCap.NONE
    
    # For opening delimiter, right side should not have space.
    can_open = cursor.is_not_whitespace(current_pos+1) and can_open
    
    # For closing delimiter, left side should not have space.
    can_close = cursor.is_not_whitespace(current_pos-1)

    if can_open:
        cap |= DelimiterCap.CAN_OPEN

    if can_close:
        cap |= DelimiterCap.CAN_CLOSE


    return MatchContext(
        delimiter_cap=cap,
        token_start=current_pos,
        token_end=current_pos,
    )

    
    
class BetweenMatcher(Matcher):

    def __init__(
        self, 
        ch: str, 
        container_kind: InlineContainer, 
        fallback_leaf: InlineLeaf,
    ):
        self.ch = ch
        self.container_kind = container_kind
        self.fallback_leaf = fallback_leaf

    def get_fallback_kind(self, ctx: MatchContext) -> InlineLeaf:
        return self.fallback_leaf

    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        
        # TODO: I think the complexity here might
        # comes largely from not combinng brace and delimiter into a single token.
        ctx = self._match_context(state, pos, endpos)

        d = self.ch
        if ctx.has_close_marker:
            d = '{' + d

        openers = state.get_openers(d)

        # A delimiter could be both can_open and can_close.
        # In such case, we need to try to find opener for it.
        # If there is no opener, fallback to can_open, and then fallback to leaf.
        if ctx.can_close and openers:
            
            opener = openers[-1]
            newpos = self._handle_closer(state, pos, ctx, opener)
            if newpos is not None:
                return newpos

        if ctx.can_open:
            return self._handle_opener(state, pos, ctx)

        state.push_event(
            Event.leaf(
                Range(pos, ctx.token_end),
                kind=self.get_fallback_kind(ctx),
            )
        )

        return ctx.token_end+1

    def _handle_closer(
        self, 
        state: InlineState,
        pos: int,
        ctx: MatchContext,
        opener: OpenerV2,
    ) -> Optional[int]:
        # For example, `**` should not produce a container.
        if opener.endpos == pos-1: # exlude empty emph
            return None

        # When we reach here, there's content between opening and closing markers.
        # When inside a link destination, don't match openers from outside
        # the link construct (before the [ that started this link)
        if state.is_cross_link_boudnary(opener.startpos):
            state.push_event(
                Event.leaf(
                    Range(pos, ctx.token_end),
                    kind=self.get_fallback_kind(ctx),
                )
            )
            return ctx.token_end+1
            # fallthrough
        
        state.clear_openers(opener.startpos, pos)
        state.replace_event(
            Event.enter(
                Range(opener.startpos, opener.endpos),
                kind=self.container_kind,
            ),
            opener.event_index,
        )
        state.push_event(
            Event.exit(
                Range(pos, ctx.token_end),
                kind=self.container_kind,
            )
        )
        return ctx.token_end+1


    def _handle_opener(
        self,
        state: InlineState,
        pos: int,
        ctx: MatchContext,
    ) -> Optional[int]:
        e = self.ch
        if ctx.has_open_marker:
            e = '{' + e # TODO: <- pop last event here

        # TODO: at this point you have an Event({), Event(DELIMITER)?
        state.add_opener(
            name=e,
            default_event=Event.leaf(
                span=Range(ctx.token_start, pos),
                kind=self.get_fallback_kind(ctx),
            )
        )

        return pos+1


    def can_open(self, cursor: InputText, pos: int) -> bool:
        return True

    def _match_context(
        self,
        state: InlineState,
        pos: int,
        endpos: int
    ) -> MatchContext:
        ctx = determine_brace_context(
            cursor=state.cursor,
            current_pos=pos,
            endpos=endpos,
            last_event=state.last_event,
        )

        if ctx:
            return ctx

        return determine_bare_context(
            cursor=state.cursor,
            current_pos=pos,
            can_open=self.can_open(state.cursor, pos)
        )
        

class SubscriptMatcher(BetweenMatcher):
    def __init__(self):
        super().__init__(
            ch='~', 
            container_kind=InlineContainer.SUBSCRIPT, 
            fallback_leaf=InlineLeaf.STR,
        )

class SuperscriptMatcher(BetweenMatcher):
    def __init__(self):
        super().__init__(
            ch='^',
            container_kind=InlineContainer.SUPERSCRIPT,
            fallback_leaf=InlineLeaf.STR
        )

class EmphMatcher(BetweenMatcher):
    def __init__(self):
        super().__init__(
            ch='_',
            container_kind=InlineContainer.EMPH, 
            fallback_leaf=InlineLeaf.STR,
        )

class StrongMatcher(BetweenMatcher):
    def __init__(self):
        super().__init__(
            ch='*',
            container_kind=InlineContainer.STRONG,
            fallback_leaf=InlineLeaf.STR
        )

class InsertMatcher(BetweenMatcher):
    def __init__(self):
        super().__init__(
            ch='+', 
            container_kind=InlineContainer.INSERT, 
            fallback_leaf=InlineLeaf.STR,
        )

    def can_open(self, cursor: InputText, pos: int) -> bool:
        return cursor.has_brace(pos)

class MarkMatcher(BetweenMatcher):
    def __init__(self):
        super().__init__(
            ch='=', 
            container_kind=InlineContainer.MARK, 
            fallback_leaf=InlineLeaf.STR,
        )

class SingleQuoteMatcher(BetweenMatcher):
    def __init__(self):
        super().__init__(
            ch="'",
            container_kind=InlineContainer.SINGLE_QUOTED,
            fallback_leaf=InlineLeaf.RIGHT_SINGLE_QUOTE, # default to right single quote due to our writing habits.
        )

    def get_fallback_kind(self, ctx: MatchContext) -> InlineLeaf:
        if ctx.has_open_marker:
            return InlineLeaf.LEFT_SINGLE_QUOTE

        if ctx.has_close_marker:
            return InlineLeaf.RIGHT_SINGLE_QUOTE

        return self.fallback_leaf

    def can_open(self, cursor: InputText, pos: int) -> bool:
        return cursor.can_open_single_quote(pos-1)

class DoubleQuoteMatcher(BetweenMatcher):
    def __init__(self):
        super().__init__(
            ch='"',
            container_kind=InlineContainer.DOUBLE_QUOTED,
            fallback_leaf=InlineLeaf.LEFT_DOUBLE_QUOTE,
        )

    def get_fallback_kind(self, ctx: MatchContext) -> InlineLeaf:
        if ctx.has_open_marker:
            return InlineLeaf.LEFT_DOUBLE_QUOTE

        if ctx.has_close_marker:
            return InlineLeaf.RIGHT_DOUBLE_QUOTE

        return self.fallback_leaf