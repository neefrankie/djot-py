from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Dict, List, Literal, Protocol, Tuple, TypeGuard, TypeVar, runtime_checkable

type Attributes = Dict[str, str]

class AstNode(ABC):
    pass

@dataclass
class SourceLoc:
    line: int
    col: int
    offset: int

@dataclass
class Pos:
    start: SourceLoc
    end: SourceLoc

@dataclass
class HasAttributes:
    attributes: Attributes | None
    auto_attributes: Attributes | None
    pos: Pos | None

T = TypeVar("T")

@runtime_checkable
class HasChildren(Protocol[T]):
    children: List[T] | Tuple[T, ...]

@dataclass
class HasText:
    text: str

# === Inline ===

class InlineNode(AstNode):
    pass

@dataclass
class Str(HasAttributes, HasText, InlineNode):
    tag: Literal['str'] = 'str'

@dataclass
class SoftBreak(HasAttributes, InlineNode):
    tag = 'soft_break'

@dataclass
class HardBreak(HasAttributes, InlineNode):
    tag = 'hard_break'

@dataclass
class NonBreakingSpace(HasAttributes, InlineNode):
    tag = 'non_breaking_space'

@dataclass
class Symb(HasAttributes, InlineNode):
    tag = 'symb'
    alias: str

@dataclass
class Verbatim(HasAttributes, HasText, InlineNode):
    """
    Verbatim content begins with a string of consecutive characters ` and 
    ends with an equal-lengthed string of consecutive backtick characters.
    `` Verbatim with a backtick ` character``
    """
    tag = 'verbatim'

@dataclass
class RawInline(HasAttributes, HasText, InlineNode):
    """
    Raw inlien content in any format may be included using a verbatim
    span followed by  {=FORMAT}:

    This is `<?php echo 'Hello world! ?>`{=html}.
    """
    tag = 'raw_inline'
    format: str

@dataclass
class InlineMath(HasAttributes, HasText, InlineNode):
    """
    Einstein derived $`e=mc^2`
    """
    tag = 'inline_math'

@dataclass
class DisplayMath(HasAttributes, HasText, InlineNode):
    """
    $$` x^n + y^n = z^n `
    """
    tag = 'display_math'

@dataclass
class Url(HasAttributes, HasText, InlineNode):
    """
    <https://pandoc.org/lua-filters>
    """
    tag = 'url'

@dataclass
class Email(HasAttributes, HasText, InlineNode):
    """
    <me@example.com>
    """
    tag = 'email'

@dataclass
class FootnoteReference(HasAttributes, HasText, InlineNode):
    """
    Here is the reference.[^foo]
    """
    tag = 'footnote_reference'

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
    tag = 'smart_punctuation'
    type: SmartPunctuationType

@dataclass
class Emph(HasAttributes, InlineNode):
    tag = 'emph'
    children: List[InlineNode]

@dataclass
class Strong(HasAttributes, InlineNode):
    tag = 'strong'
    children: List[InlineNode]

@dataclass
class Link(HasAttributes, HasChildren[InlineNode], InlineNode):
    """
    Inline link: [My link text](http://example.com)
    Reference link: [My link text][foo bar]
    [foo bar]: http://example.com

    [My link text][]
    [My link text]: /url
    """
    tag = 'link'
    destination: str | None
    reference: str | None

@dataclass
class Image(HasAttributes, HasChildren[InlineNode], InlineNode):
    """
    Inline:

    ![picture of a cat](cat.jpg)

    Reference variants:

    ![picture of a cat][cat] 
    ![cat][]

    [cat]: feline.jpg
    """
    tag = 'image'
    destination: str | None
    reference: str | None

@dataclass
class Span(HasAttributes, InlineNode):
    """
    I can be helpful to [read the manual]{.big .red}.
    """
    tag = 'span'
    children: List[InlineNode]

@dataclass
class Mark(HasAttributes, InlineNode):
    tag = 'mark'
    children: List[InlineNode]

@dataclass
class Superscript(HasAttributes, InlineNode):
    """
    djot^TM^
    """
    tag = 'superscript'
    children: List[InlineNode]

@dataclass
class Subscript(HasAttributes, InlineNode):
    """
    H~2~O
    """
    tag = 'subscript'
    children: List[InlineNode]

@dataclass
class Insert(HasAttributes, InlineNode):
    """
    {+nice+}
    """
    tag = 'insert'
    children: List[InlineNode]

@dataclass
class Delete(HasAttributes, InlineNode):
    """
    {-mean-}
    """
    tag = 'delete'
    children: List[InlineNode]

@dataclass
class DoubleQuoted(HasAttributes, InlineNode):
    tag = 'double_quoted'
    children: List[InlineNode]

@dataclass
class SingleQuoted(HasAttributes, InlineNode):
    tag = 'single_quoted'
    children: List[InlineNode]

# === Block ===

class BlockNode(AstNode):
    pass

@dataclass
class Para(HasAttributes,  BlockNode):
    tag = 'para'
    children: List[BlockNode]

@dataclass
class Heading(HasAttributes, BlockNode):
    tag = 'heading'
    level: int
    children: List[InlineNode]

@dataclass
class ThematicBreak(HasAttributes, BlockNode):
    tag = 'thematic_break'

@dataclass
class Section(HasAttributes, BlockNode):
    tag = 'section'
    children: List[BlockNode]

@dataclass
class Div(HasAttributes, BlockNode):
    tag = 'div'
    children: List[BlockNode]

@dataclass
class BlockQuote(HasAttributes, BlockNode):
    tag = 'block_quote'
    children: List[BlockNode]

@dataclass
class CodeBlock(HasAttributes, HasText, BlockNode):
    tag = 'code_block'
    lang: str | None

@dataclass
class RawBlock(HasAttributes, HasText, BlockNode):
    tag = 'raw_block'
    format: str


# === List ===
class BulletListStyle(StrEnum):
    PLUS = '+'
    DASH = '-'
    STAR = '*'

class ListItem(HasAttributes, AstNode):
    tag = 'list_item'
    children: List[BlockNode]

@dataclass
class BulletList(HasAttributes, BlockNode):
    tag = 'bullet_list'
    tight: bool
    style: BulletListStyle
    children: List[ListItem]

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
    tag = 'ordered_list'
    style: OrderedListStyle
    tight: bool
    start: int | None
    children: List[ListItem]

class CheckboxStatus(Enum):
    CHECKED = 0
    UNCHECKED = 1

@dataclass
class TaskListItem(HasAttributes, AstNode):
    tag = 'task_list_item'
    status: CheckboxStatus
    children: List[BlockNode]

@dataclass
class TaskList(HasAttributes, BlockNode):
    tag = 'task_list'
    tight: bool
    children: List[TaskListItem]

# === Definition List ===

@dataclass
class Term(HasAttributes, AstNode):
    tag = 'term'
    children: List[InlineNode]

@dataclass
class Definition(HasAttributes, AstNode):
    tag = 'definition'
    children: List[InlineNode]

@dataclass
class DefinitionListItem(HasAttributes, AstNode):
    tag = 'definition_list_item'
    children: Tuple[Term, Definition]

@dataclass
class DefinitionList(HasAttributes, BlockNode):
    tag = 'definition_list'
    children: List[DefinitionListItem]

# === Table ===
class Alignment(Enum):
    Default = 0
    Left = 1
    Right = 2
    Center = 3

@dataclass
class Cell(HasAttributes, AstNode):
    tag = 'cell'
    head: bool
    align: Alignment
    children: List[InlineNode]

@dataclass
class Row(HasAttributes, AstNode):
    tag = 'row'
    head: bool
    children: List[Cell]

@dataclass
class Caption(HasAttributes):
    tag = 'caption'
    children: List[InlineNode]

@dataclass
class Table(HasAttributes, BlockNode):
    tag = 'table'
    caption: Caption
    children: List[Row]


@dataclass
class Reference(HasAttributes, AstNode):
    tag = 'reference'
    label: str
    destination: str

@dataclass
class Footnote(HasAttributes, AstNode):
    tag = 'footnote'
    label: str
    children: List[BlockNode]

@dataclass
class Doc(HasAttributes, AstNode):
    tag = 'doc'
    references: Dict[str, Reference]
    auto_references: Dict[str, Reference]
    footnotes: Dict[str, Footnote]
    children: List[BlockNode]


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
        case Row(head=_):  # 只要 Row 有 head 属性就匹配
            return True
        case _:
            return False

def is_caption(node: Row | Caption) -> TypeGuard[Caption]:
    match node:
        case Row(head=_):
            return False
        case _:  # 不是 Row 就一定是 Caption
            return True