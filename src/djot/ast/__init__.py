from abc import ABC, abstractmethod
from typing import TypeGuard, TypeVar

from .base import (
    AstNode,
    BlockNode,
    InlineNode,
    HasChildren,
    HasText,
    ContentBlock,
    DefinitionBlock,
)
from .doc import Doc
from .block import (
    Para,
    Heading,
    ThematicBreak,
    Section,
    Div,
    CodeBlock,
    RawBlock,
    BlockQuote,
    Footnote,
    Reference
)
from .list import (
    OrderedList,
    BulletList,
    TaskList,
    DefinitionList,
    ListItem,
    TaskListItem,
    DefinitionListItem,
    Term,
    Definition,
)
from .table import (
    Table,
    Caption,
    Row,
    Cell,
)
from .inline import (
    Str,
    SoftBreak,
    HardBreak,
    NonBreakingSpace,
    Symb,
    Verbatim,
    RawInline,
    InlineMath,
    DisplayMath,
    Url,
    Email,
    FootnoteReference,
    SmartPunctuation,
    Emph,
    Strong,
    Link,
    Image,
    Span,
    Mark,
    Superscript,
    Subscript,
    Insert,
    Delete,
    DoubleQuoted,
    SingleQuoted,
)


C = TypeVar('C')
R = TypeVar('R')

class Visitor[C, R](ABC):
    @abstractmethod
    def doc(self, node: Doc, context: C) -> R:
        pass

    @abstractmethod
    def para(self, node: Para, context: C) -> R:
        pass

    @abstractmethod
    def heading(self, node: Heading, context: C) -> R:
        pass

    @abstractmethod
    def thematic_break(self, node: ThematicBreak, context: C) -> R:
        pass

    @abstractmethod
    def section(self, node: Section, context: C) -> R:
        pass

    @abstractmethod
    def div(self, node: Div, context: C) -> R:
        pass

    @abstractmethod
    def code_block(self, node: CodeBlock, context: C) -> R:
        pass

    @abstractmethod
    def raw_block(self, node: RawBlock, context: C) -> R:
        pass

    @abstractmethod
    def block_quote(self, node: BlockQuote, context: C) -> R:
        pass

    @abstractmethod
    def ordered_list(self, node: OrderedList, context: C) -> R:
        pass

    @abstractmethod
    def bullet_list(self, node: BulletList, context: C) -> R:
        pass

    @abstractmethod
    def task_list(self, node: TaskList, context: C) -> R:
        pass

    @abstractmethod
    def definition_list(self, node: DefinitionList, context: C) -> R:
        pass

    @abstractmethod
    def table(self, node: Table, context: C) -> R:
        pass

    @abstractmethod
    def str(self, node: Str, context: C) -> R:
        pass

    @abstractmethod
    def soft_break(self, node: SoftBreak, context: C) -> R:
        pass

    @abstractmethod
    def hard_break(self, node: HardBreak, context: C) -> R:
        pass

    @abstractmethod
    def non_breaking_space(self, node: NonBreakingSpace, context: C) -> R:
        pass

    @abstractmethod
    def symb(self, node: Symb, context: C) -> R:
        pass

    @abstractmethod
    def verbatim(self, node: Verbatim, context: C) -> R:
        pass

    @abstractmethod
    def raw_inline(self, node: RawInline, context: C) -> R:
        pass

    @abstractmethod
    def display_math(self, node: DisplayMath, context: C) -> R:
        pass

    @abstractmethod
    def url(self, node: Url, context: C) -> R:
        pass

    @abstractmethod
    def email(self, node: Email, context: C) -> R:
        pass

    @abstractmethod
    def footnote_reference(self, node: FootnoteReference, context: C) -> R:
        pass

    @abstractmethod
    def smart_punctuation(self, node: SmartPunctuation, context: C) -> R:
        pass

    @abstractmethod
    def emph(self, node: Emph, context: C) -> R:
        pass

    @abstractmethod
    def strong(self, node: Strong, context: C) -> R:
        pass

    @abstractmethod
    def link(self, node: Link, context: C) -> R:
        pass

    @abstractmethod
    def image(self, node: Image, context: C) -> R:
        pass

    @abstractmethod
    def span(self, node: Span, context: C) -> R:
        pass

    @abstractmethod
    def mark(self, node: Mark, context: C) -> R:
        pass

    @abstractmethod
    def superscript(self, node: Superscript, context: C) -> R:
        pass

    @abstractmethod
    def subscript(self, node: Subscript, context: C) -> R:
        pass

    @abstractmethod
    def insert(self, node: Insert, context: C) -> R:
        pass

    @abstractmethod
    def delete(self, node: Delete, context: C) -> R:
        pass

    @abstractmethod
    def double_quoted(self, node: DoubleQuoted, context: C) -> R:
        pass

    @abstractmethod
    def single_quoted(self, node: SingleQuoted, context: C) -> R:
        pass

    @abstractmethod
    def list_item(self, node: ListItem, context: C) -> R:
        pass

    @abstractmethod
    def task_list_item(self, node: TaskListItem, context: C) -> R:
        pass

    @abstractmethod
    def definition_list_item(self, node: DefinitionListItem, context: C) -> R:
        pass

    @abstractmethod
    def term(self, node: Term, context: C) -> R:
        pass

    @abstractmethod
    def definition(self, node: Definition, context: C) -> R:
        pass

    @abstractmethod
    def row(self, node: Row, context: C) -> R:
        pass

    @abstractmethod
    def cell(self, node: Cell, context: C) -> R:
        pass
    
    @abstractmethod
    def caption(self, node: Caption, context: C) -> R:
        pass

    @abstractmethod
    def footnote(self, node: Footnote, context: C) -> R:
        pass

    @abstractmethod
    def reference(self, node: Reference, context: C) -> R:
        pass

def is_block(node: AstNode) -> TypeGuard[BlockNode]:
    match node:
        case (
            Para()
            | Heading()
            | BlockQuote()
            | ThematicBreak()
            | Section()
            | Div()
            | CodeBlock()
            | RawBlock()
            | BulletList()
            | OrderedList()
            | TaskList()
            | DefinitionList()
            | Table()
            | Reference()
            | Footnote()
        ):
            return True
        
        case _:
            return False

def is_inline(node: AstNode) -> bool:
    match node:
        case (
            Str()
            | SoftBreak()
            | HardBreak()
            | NonBreakingSpace()
            | Symb()
            | Verbatim()
            | RawInline()
            | InlineMath()
            | DisplayMath()
            | Url()
            | Email()
            | FootnoteReference()
            | SmartPunctuation()
            | Emph()
            | Strong()
            | Link()
            | Image()
            | Span()
            | Mark()
            | Superscript()
            | Subscript()
            | Insert()
            | Delete()
            | DoubleQuoted()
            | SingleQuoted()
        ):
            return True
        
        case _:
            return False
        

def is_row(node: Row | Caption) -> TypeGuard[Row]:
    match node:
        case Row(head=_):
            return True
        case _:
            return False

def is_caption(node: Row | Caption) -> TypeGuard[Caption]:
    match node:
        case Row(head=_):
            return False
        case _:
            return True