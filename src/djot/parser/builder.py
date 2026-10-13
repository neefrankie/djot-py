from typing import Dict, Iterator

from djot.event import (
    Event,
    EventKind,
    BlockContainer,
    InlineContainer,
    VerbatimKind,
    InlineLeaf,
    BlockLeaf,
    AttrKind,
)
from djot.ast import (
    Doc,
)

from .frame import (
    Frame,
)
from .state import (
    DocumentContext,
    BuildingState,
)
from .handler import Handler
from .handle_default import DefaultHandler
from .handle_attr import (
    InlineAttrHandler,
    BlockAttrHandler,
    AttrLeafHandler,
)
from .handle_blockquote import BlockquoteHandler
from .handle_div import DivHandler
from .handle_footnote import (
    FootnoteHandler,
    NoteLabelHandler,
    FootnoteRefHandler,
)
from .handle_heading import HeadingHandler
from .handle_link import (
    LinkTextHandler,
    ImageTextHandler,
    DestHandler,
    ReferenceHandler,
    RefDefHandler,
    ReferenceKeyHandler,
    ReferenceValueHandler,
    AutoUrlHandler,
    AutoEmailHandler,
)
from .handle_list import (
    ListHandler,
    ListItemHandler,
    CheckboxHandler,
    BlanklineHandler,
)
from .handle_para import ParaHandler
from .handle_table import (
    TableHandler,
    TableRowHandler,
    TableSeparatorHandler,
    TableCellHandler,
    CaptionHandler,
)
from .handle_thematic import ThematicBreakHandler
from .handle_verb import (
    VerbatimHandler,
    DisplayMathHandler,
    InlineMathHandler,
    RawForamtHandler,
    CodeBlockHandler,
    CodeLangHandler,
)


class ASTBuilder:
    def __init__(self, src: str, events: Iterator[Event], source_location: bool = False):
        self.events = events

        self.ctx = DocumentContext(
            src,
            source_location=source_location
        )
        self.state = BuildingState()

        self.handle_default = DefaultHandler()
        self.handle_attr = AttrLeafHandler()

        self.handlers: Dict[EventKind, Handler] = {
            InlineLeaf.FOOTNOTE_REF:    FootnoteRefHandler(),
            InlineContainer.ATTR:       InlineAttrHandler(),
            BlockContainer.ATTRIBUTES:  BlockAttrHandler(),
            InlineContainer.LINK_TEXT:  LinkTextHandler(),
            InlineContainer.IMAGE_TEXT: ImageTextHandler(),
            InlineContainer.DESTINATION: DestHandler(),
            InlineContainer.REFERENCE:  ReferenceHandler(),
            BlockContainer.REFERENCE_DEFINITION: RefDefHandler(),
            InlineLeaf.REFERENCE_KEY:   ReferenceKeyHandler(),
            InlineLeaf.REFERENCE_VALUE: ReferenceValueHandler(),
            VerbatimKind.VERBATIM:      VerbatimHandler(),
            InlineLeaf.RAW_FORMAT:      RawForamtHandler(),
            VerbatimKind.DISPLAY_MATH:  DisplayMathHandler(),
            VerbatimKind.INLINE_MATH:   InlineMathHandler(),
            InlineContainer.URL:        AutoUrlHandler(),
            InlineContainer.EMAIL:      AutoEmailHandler(),
            BlockContainer.PARA:        ParaHandler(),
            BlockContainer.HEADING:     HeadingHandler(),
            BlockContainer.LIST:        ListHandler(),
            BlockContainer.LIST_ITEM:   ListItemHandler(),
            InlineLeaf.CHECKBOX:        CheckboxHandler(),
            BlockContainer.BLOCK_QUOTE: BlockquoteHandler(),
            BlockContainer.TABLE:       TableHandler(),
            BlockContainer.TABLE_ROW:   TableRowHandler(),
            InlineLeaf.SOFT_BREAK:      TableSeparatorHandler(),
            InlineContainer.TABLE_CELL: TableCellHandler(),
            BlockContainer.CAPTION:     CaptionHandler(),
            BlockContainer.FOOTNOTE:    FootnoteHandler(),
            InlineLeaf.NOTE_LABEL:      NoteLabelHandler(),
            BlockContainer.CODE_BLOCK:  CodeBlockHandler(),
            InlineLeaf.CODE_LANGUAGE:   CodeLangHandler(),
            BlockContainer.DIV:         DivHandler(),
            BlockLeaf.THEMATIC_BREAK:   ThematicBreakHandler(),
            BlockLeaf.BLANKLINE:        BlanklineHandler(),
        }


    def build(self):
        root_frame = Frame(
            kind=BlockContainer.DOC,
            start_pos=0,
            children=[],
        )
        self.state.push_frame(root_frame)

        last_pos = 0
        for event in self.events:
            self._dispatch_event(event)
            last_pos = event.endpos

        last_loc = self.ctx.calc_loc(last_pos)

        doc = Doc(
            children=root_frame.pop_block_children(),
            references=self.state.references.copy(),
            footnotes=self.state.footnotes.copy(),
        )

        if not root_frame.attributes.is_empty:
            doc.attributes = root_frame.attributes.build()

        return doc

    def _dispatch_event(self, event: Event):

        if event.kind in AttrKind:
            self.handle_attr(self.state, self.ctx, event)
            return
        
        if event.kind in self.handlers:
            handler = self.handlers[event.kind]
            handler(self.state, self.ctx, event)
        else:
            self.handle_default(self.state, self.ctx, event)

