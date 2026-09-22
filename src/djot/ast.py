from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Dict, List, Protocol, Tuple, TypeGuard, TypeVar, runtime_checkable

from .common import SourceLoc

@dataclass
class Pos:
    start: SourceLoc
    end: SourceLoc

type Attributes = Dict[str, str]

@dataclass
class AstNode(ABC):
    tag: str


@dataclass
class HasAttributes:
    attributes: Attributes | None
    auto_attributes: Attributes | None
    pos: Pos | None

T = TypeVar("T")

@runtime_checkable
class HasChildren(Protocol[T]):
    # children: List[T] | Tuple[T, ...] # why there is a tuple?
    children: List[T]

@dataclass
class HasText:
    text: str

# === Inline ===

class InlineNode(AstNode):
    pass

@dataclass
class Str(HasAttributes, HasText, InlineNode):
    tag: str = 'str'

@dataclass
class SoftBreak(HasAttributes, InlineNode):
    tag: str = 'soft_break'

@dataclass
class HardBreak(HasAttributes, InlineNode):
    tag: str = 'hard_break'

@dataclass
class NonBreakingSpace(HasAttributes, InlineNode):
    tag: str = 'non_breaking_space'

@dataclass
class Symb(HasAttributes, InlineNode):
    alias: str
    tag: str = 'symb'
    
@dataclass
class Verbatim(HasAttributes, HasText, InlineNode):
    """
    Verbatim content begins with a string of consecutive characters ` and 
    ends with an equal-lengthed string of consecutive backtick characters.
    `` Verbatim with a backtick ` character``
    """
    tag: str = 'verbatim'

@dataclass
class RawInline(HasAttributes, HasText, InlineNode):
    """
    Raw inlien content in any format may be included using a verbatim
    span followed by  {=FORMAT}:

    This is `<?php echo 'Hello world! ?>`{=html}.
    """

    format: str
    tag: str = 'raw_inline'

@dataclass
class InlineMath(HasAttributes, HasText, InlineNode):
    """
    Einstein derived $`e=mc^2`
    """
    tag: str = 'inline_math'

@dataclass
class DisplayMath(HasAttributes, HasText, InlineNode):
    """
    $$` x^n + y^n = z^n `
    """
    tag: str = 'display_math'

@dataclass
class Url(HasAttributes, HasText, InlineNode):
    """
    <https://pandoc.org/lua-filters>
    """
    tag: str = 'url'

@dataclass
class Email(HasAttributes, HasText, InlineNode):
    """
    <me@example.com>
    """
    tag: str = 'email'

@dataclass
class FootnoteReference(HasAttributes, HasText, InlineNode):
    """
    Here is the reference.[^foo]
    """
    tag: str = 'footnote_reference'

class SmartPunctuationType(Enum):
    LEFT_SINGLE_QUOTE = 0
    RIGHT_SINGLE_QUOTE = 1
    LEFT_DOUBLE_QUOTE = 2
    RIGHT_DOUBLE_QUOTE = 3
    ELLIPSES = 4
    EM_DASH = 5
    EN_DASH = 6

@dataclass
class SmartPunctuation(HasAttributes, HasText, InlineNode):
    type: SmartPunctuationType
    tag: str = 'smart_punctuation'

@dataclass
class Emph(HasAttributes, InlineNode):
    children: List[InlineNode]
    tag: str = 'emph'

@dataclass
class Strong(HasAttributes, InlineNode):
    children: List[InlineNode]
    tag: str = 'strong'

@dataclass
class Link(HasAttributes, InlineNode):
    """
    Inline link: [My link text](http://example.com)
    Reference link: [My link text][foo bar]
    [foo bar]: http://example.com

    [My link text][]
    [My link text]: /url
    """
    
    destination: str | None
    reference: str | None
    children: List[InlineNode]
    tag: str = 'link'

@dataclass
class Image(HasAttributes, InlineNode):
    """
    Inline:

    ![picture of a cat](cat.jpg)

    Reference variants:

    ![picture of a cat][cat] 
    ![cat][]

    [cat]: feline.jpg
    """
    
    destination: str | None
    reference: str | None
    children: List[InlineNode]
    tag: str = 'image'

@dataclass
class Span(HasAttributes, InlineNode):
    """
    I can be helpful to [read the manual]{.big .red}.
    """
    
    children: List[InlineNode]
    tag: str = 'span'

@dataclass
class Mark(HasAttributes, InlineNode):
    children: List[InlineNode]
    tag: str = 'mark'

@dataclass
class Superscript(HasAttributes, InlineNode):
    """
    djot^TM^
    """
    
    children: List[InlineNode]
    tag: str = 'superscript'

@dataclass
class Subscript(HasAttributes, InlineNode):
    """
    H~2~O
    """
    
    children: List[InlineNode]
    tag: str = 'subscript'

@dataclass
class Insert(HasAttributes, InlineNode):
    """
    {+nice+}
    """
    
    children: List[InlineNode]
    tag: str = 'insert'

@dataclass
class Delete(HasAttributes, InlineNode):
    """
    {-mean-}
    """
    
    children: List[InlineNode]
    tag: str = 'delete'

@dataclass
class DoubleQuoted(HasAttributes, InlineNode):
    children: List[InlineNode]
    tag: str = 'double_quoted'

@dataclass
class SingleQuoted(HasAttributes, InlineNode):
    children: List[InlineNode]
    tag: str = 'single_quoted'

# === Block ===

class BlockNode(AstNode):
    pass

@dataclass
class Para(HasAttributes, BlockNode):
    children: List[BlockNode]
    tag: str = 'para'

@dataclass
class Heading(HasAttributes, BlockNode):
    level: int
    children: List[InlineNode]
    tag: str = 'heading'

@dataclass
class ThematicBreak(HasAttributes, BlockNode):
    tag: str = 'thematic_break'

@dataclass
class Section(HasAttributes, BlockNode):
    children: List[BlockNode]
    tag: str = 'section'

@dataclass
class Div(HasAttributes, BlockNode):
    children: List[BlockNode]
    tag: str = 'div'

@dataclass
class BlockQuote(HasAttributes, BlockNode):
    children: List[BlockNode]
    tag: str = 'block_quote'

@dataclass
class CodeBlock(HasAttributes, HasText, BlockNode):
    lang: str | None
    tag: str = 'code_block'

@dataclass
class RawBlock(HasAttributes, HasText, BlockNode):
    format: str
    tag: str = 'raw_block'


# === List ===
class BulletListStyle(StrEnum):
    PLUS = '+'
    DASH = '-'
    STAR = '*'

class ListItem(HasAttributes, AstNode):
    children: List[BlockNode]
    tag: str = 'list_item'

@dataclass
class BulletList(HasAttributes, BlockNode):
    tight: bool
    style: BulletListStyle
    children: List[ListItem]
    tag: str = 'bullet_list'

class OrderedListStyle(StrEnum):
    NUMBER = '1.'
    NUM_RPAREN = '1)'
    NUM_PAREN = '(1)'
    LOWER_ALPHA = 'a.'
    LOWER_ALPHA_RPAREN = 'a)'
    LOWER_ALPHA_PAREN = '(a)'
    UPPER_ALPHA = 'A.'
    UPPER_ALPHA_RPAREN = 'A)'
    UPPER_ALPHA_PAREN = '(A)'
    LOWER_ROMAN = 'i.'
    LOWER_ROMAN_RPAREN = 'i)'
    LOWER_ROMAN_PAREN = '(i)'
    UPPER_ROMAN = 'I.'
    UPPER_ROMAN_RPAREN = 'I)'
    UPPER_ROMAN_PAREN = '(I)'

@dataclass
class OrderedList(HasAttributes, BlockNode):
    style: OrderedListStyle
    tight: bool
    start: int | None
    children: List[ListItem]
    tag: str = 'ordered_list'

class CheckboxStatus(Enum):
    CHECKED = 0
    UNCHECKED = 1

@dataclass
class TaskListItem(HasAttributes, AstNode):
    status: CheckboxStatus
    children: List[BlockNode]
    tag: str = 'task_list_item'

@dataclass
class TaskList(HasAttributes, BlockNode):
    tight: bool
    children: List[TaskListItem]
    tag: str = 'task_list'

# === Definition List ===

@dataclass
class Term(HasAttributes, AstNode):
    children: List[InlineNode]
    tag: str = 'term'

@dataclass
class Definition(HasAttributes, AstNode):
    children: List[InlineNode]
    tag: str = 'definition'

@dataclass
class DefinitionListItem(HasAttributes, AstNode):
    children: Tuple[Term, Definition]
    tag: str = 'definition_list_item'

@dataclass
class DefinitionList(HasAttributes, BlockNode):
    children: List[DefinitionListItem]
    tag: str = 'definition_list'

# === Table ===
class Alignment(StrEnum):
    DEFAULT = 'default'
    LEFT = 'left'
    RIGHT = 'right'
    CENTER = 'center'

@dataclass
class Cell(HasAttributes, AstNode):
    head: bool
    align: Alignment
    children: List[InlineNode]
    tag: str = 'cell'

@dataclass
class Row(HasAttributes, AstNode):
    head: bool
    children: List[Cell]
    tag: str = 'row'

@dataclass
class Caption(HasAttributes):
    children: List[InlineNode]
    tag: str = 'caption'

@dataclass
class Table(HasAttributes, BlockNode):
    caption: Caption
    children: List[Row]
    tag: str = 'table'


@dataclass
class Reference(HasAttributes, AstNode):
    label: str
    destination: str
    tag: str = 'reference'

@dataclass
class Footnote(HasAttributes, AstNode):
    label: str
    children: List[BlockNode]
    tag: str = 'footnote'

@dataclass
class Doc(HasAttributes, AstNode):
    references: Dict[str, Reference]
    auto_references: Dict[str, Reference]
    footnotes: Dict[str, Footnote]
    children: List[BlockNode]
    tag: str = 'doc'


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
        
    return node.tag in inline_tags

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