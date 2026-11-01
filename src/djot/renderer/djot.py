from djot.ast import (
    Doc,
    AstNode,
    HasChildren,
    BlockNode,
    Para,
    Heading,
    Div,
    BulletList,
    OrderedList,
    TaskList,
    DefinitionList,
    Table,
    Caption,
    Row,
    BlockQuote,
    CodeBlock,
    RawBlock,
    Term,
    Definition,
    Footnote,
    Reference,
    Symb,
    Span,
    Link,
    Image,
    Email,
    Url,
    HasText,
    RawInline,
    FootnoteReference,
    InlineNode,
    SoftBreak,
    HardBreak,
    Str,
    InlineMath,
    DisplayMath,
    Verbatim,
    SmartPunctuation,
)
from djot.parser import get_string_content

def is_whitespace(node: InlineNode) -> bool:
    return isinstance(node, (SoftBreak, HardBreak))

def begins_with_whitespace(node: HasChildren[InlineNode]) -> bool:
    return (bool(node.children) and is_whitespace(node.children[0]))