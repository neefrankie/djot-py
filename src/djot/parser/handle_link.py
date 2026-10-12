from typing import Optional

from djot.ast import (
    AstNode,
    Image,
    Link,
    Reference,
    Url,
    Email,
)
from djot.event import (
    Event,
    InlineContainer,
    BlockContainer,
)

from .frame import Frame
from .normalize import (
    normalize_label
)
from .state import BuildingState, DocumentContext
from .handler import Handler
from .normalize import replace_newline

# LINK_TEXT and IMAGE_TEXT
class LinkTextHandler(Handler):
    """
    [My link text](http://example.com)
    [My link text][http://example.com]

    +LINK_TEXT
        STR
    -LINK_TEXT
    +REFERENCE
        STR
    -REFERENCE
    """
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        return Frame(
            kind=event.kind,
            start_pos=event.startpos,
            is_image=False
        )
    
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        # Do nothing when link text ends.
        return None

# InlineContainer.IMAGE_TEXT
class ImageTextHandler(Handler):
    """
    ![picture of a cat][cat.jpg]
    ![beautiful skyline](clouds.jpg)

    IMAGE_MARKER
    +IMAGE_TEXT
        STR
    -IMAGE_TEXT
    +DESTINATION
        STR
    -DESTINATION

    IMAGE_MARKER
    +IMAGE_TEXT
        STR
    -IMAGE_TEXT
    +REFERENCE
        STR
    -REFERENCE
    """
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        return Frame(
            kind=event.kind,
            start_pos=event.startpos,
            is_image=True
        )
    
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        # Do nothing when link text ends.
        return None

# InlineContainer.DESTINATION
class DestHandler(Handler):
    """
    The second part of explicit link:

    [My link text](http://example.com)
    ![beautiful skyline](clouds.jpg)
    """
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        state.switch_to_literal()
        return None

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_pos(
            frame.start_pos,
            event.endpos
        )
        dest = frame.accumulated_text

        state.switch_to_normal()

        if frame.kind == InlineContainer.IMAGE_TEXT:
            return Image(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_inline_children(),
                destination=dest,
                reference=None
            )
        elif frame.kind == InlineContainer.LINK_TEXT:
            return Link(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_inline_children(),
                destination=dest,
                reference=None,
            )
        return None

# InlineContainer.REFERENCE
class ReferenceHandler(Handler):
    """
    The second part of reference link:

    [My link text][foo bar]
    ![picture of a cat][cat]
    """
    # [My link text][foo bar]
    # ![picture of a cat][cat]
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        state.switch_to_literal()
        return None

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_pos(
            frame.start_pos,
            event.endpos
        )

        ref = frame.accumulated_text
        if not ref:
            ref = frame.get_children_text()

        if frame.kind == InlineContainer.IMAGE_TEXT:
            return Image(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_inline_children(),
                destination=None,
                reference=normalize_label(ref),
            )
        elif frame.kind == InlineContainer.LINK_TEXT:
            return Link(
                attributes=frame.attributes.build(),
                pos=pos,
                children=frame.pop_inline_children(),
                destination=None,
                reference=normalize_label(ref)
            )

        return None

class RefDefHandler(Handler):
    """
    The definition of a reference link:
    
    [foo]: bar\n baz\n

    +REFERENCE_DEFINITION
        REFERENCE_KEY
        REFERENCE_VALUE
        REFERENCE_VALUE
    -REFERENCE_DEFINITION
    """
    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Optional[AstNode]:
        frame = state.pop_frame()

        assert frame.kind == BlockContainer.REFERENCE_DEFINITION

        pos = ctx.calc_pos(
            frame.start_pos,
            event.endpos,
        )

        label_val = frame.ref_def_data
        if not label_val:
            return None

        label = normalize_label(label_val.key)

        if not label:
            return None

        state.add_reference(Reference(
            attributes=frame.attributes.build(),
            pos=pos,
            label=label,
            destination=label_val.value
        ))

        return None


class ReferenceKeyHandler(Handler):
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        key = ctx.get_text(event.startpos+1, event.endpos)
        state.current_frame.set_ref_key(key)


class ReferenceValueHandler(Handler):
    def handle_leaf(self, state: BuildingState, ctx: DocumentContext, event: Event):
        val = ctx.get_text(event.startpos, event.endpos+1)
        state.current_frame.set_ref_val(val)

# InlineContainer.URL
class AutoUrlHandler(Handler):
    """
    <https://pandoc.org/lua-filters>
    """
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        state.switch_to_literal()
        return super().on_enter(state, ctx, event)

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_container_pos(frame, event)
        text = replace_newline(frame.accumulated_text)
        state.switch_to_normal()

        return Url(
            attributes=frame.attributes.build(),
            pos=pos,
            text=text
        )

# InlineContainer.EMAIL
class AutoEmailHandler(Handler):
    """
    <me@example.com>
    """
    def on_enter(self, state: BuildingState, ctx: DocumentContext, event: Event) -> Frame | None:
        state.switch_to_literal()
        return Frame(
            kind=event.kind,
            start_pos=event.startpos
        )

    def on_exit(self, state: BuildingState, ctx: DocumentContext, event: Event) -> AstNode | None:
        frame = state.pop_frame()
        pos = ctx.calc_pos(
            frame.start_pos,
            event.endpos
        )
        text = replace_newline(frame.accumulated_text)
        state.switch_to_normal()

        return Email(
            attributes=frame.attributes.build(),
            pos=pos,
            text=text
        )