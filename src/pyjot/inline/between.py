from dataclasses import dataclass
from enum import Enum, IntFlag, auto
from typing import Optional

from ..common import (
    Range,
)
from ..event import (
    Event,
    BlockLeaf,
    InlineContainer,
    InlineLeaf,
)
from ..input import InputText
from .matcher import Matcher
from .state import InlineState, Opener

class DelimiterCap(IntFlag):
    """Position of delimiter relative to space
    
    Correspond to can_open and can_close in djot.js implementation
    """
    NONE = 0 # False, Fase. ` * `
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
    startopener: int
    endcloser: int
    marker_style: MarkerStyle = MarkerStyle.NONE

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

    def __call___(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        ctx = self.match_context(state, pos, endpos)

        d = self.ch
        if ctx.has_open_marker:
            d = '{' + d

        openers = state.get_openers(d)

        # A delimiter could be both can_open and can_close.
        # In such case, we need to try to find opener for it.
        # If there is no opener, fallback to can_open, and then fallback to leaf.
        if ctx.can_close and openers:
            opener = openers[-1]
            newpos = self._handle_closer(state, ctx, opener, pos)
            if newpos is not None:
                return newpos

        if ctx.can_open:
            return self._handle_opener(state, ctx, pos)

        state.push_event(
            Event.leaf(
                Range(pos, ctx.endcloser),
                kind=self.get_fallback_kind(ctx),
            )
        )

        return ctx.endcloser+1

    def _handle_closer(
        self, 
        state: InlineState, 
        ctx: MatchContext, 
        opener: Opener, 
        pos: int
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
                    Range(pos, ctx.endcloser),
                    kind=self.get_fallback_kind(ctx),
                )
            )
            return ctx.endcloser+1
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
                Range(pos, ctx.endcloser),
                kind=self.container_kind,
            )
        )
        return ctx.endcloser+1


    def _handle_opener(
        self, 
        state: InlineState, 
        ctx: MatchContext, 
        pos: int
    ) -> Optional[int]:
        e = self.ch
        if ctx.has_open_marker:
            e = '{' + e

        state.add_opener(
            name=e,
            default_event=Event.leaf(
                span=Range(pos, pos),
                kind=self.get_fallback_kind(ctx),
            )
        )

        return pos+1


    def can_open(self, cursor: InputText, pos: int) -> bool:
        return True

    def match_context(
        self,
        state: InlineState,
        pos: int,
        endpos: int
    ) -> MatchContext:
        ctx = self.brace_context(state, pos, endpos)
        if ctx:
            return ctx

        return self.bare_context(state.cursor, pos)

    def bare_context(
        self,
        cursor: InputText,
        pos: int
    ) -> MatchContext:
        cap = DelimiterCap.NONE

        # For opening delimiter, right side should not have space.
        can_open = (not cursor.is_whitespace(pos+1)) and self.can_open(cursor, pos)
        
        # For closing delimiter, left side should not have space.
        can_close = not cursor.is_whitespace(pos-1)

        if can_open:
            cap |= DelimiterCap.CAN_OPEN

        if can_close:
            cap |= DelimiterCap.CAN_CLOSE


        return MatchContext(
            delimiter_cap=cap,
            startopener=pos,
            endcloser=pos,
        )

    def brace_context(
        self,
        state: InlineState,
        pos: int,
        endpos: int
    ):
        last_event = state.last_event
        has_opener_brace = last_event and last_event.is_open_marker
        if has_opener_brace:
            return MatchContext(
                delimiter_cap=DelimiterCap.CAN_OPEN,
                startopener=pos-1,
                endcloser=pos,
                marker_style=MarkerStyle.OPEN,
            )
        
        has_close_marker = pos+1 <= endpos and state.cursor.is_right_brace(pos+1)

        if has_close_marker:
            return MatchContext(
                delimiter_cap=DelimiterCap.CAN_CLOSE,
                startopener=pos,
                endcloser=pos+1,
                marker_style=MarkerStyle.CLOSE,
            )

        return None

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