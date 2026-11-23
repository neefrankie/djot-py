import re
from typing import List

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
    return (
        bool(node.children)
        and is_whitespace(node.children[0])
    )

def ends_with_whitespace(node: HasChildren[InlineNode]) -> bool:
    return (
        bool(node.children)
        and is_whitespace(node.children[-1])
    )

PATT_BACKTICK = re.compile(r'(`+)')

def verbatim_delim(node: HasText, minticks: int) -> str:
    """
    Determine verbatim delimiter based on how many
    literal backtick in the enclosed text.

    As the enclosing delimiter should always have
    more backtick chars than thosee encountered in
    the enclosed text, we should find out the each
    consecutive sequence of literal backtick chars
    used in text and ensure the enclosing delimiter
    does not conflict with them.

    For example, if content is '`` var ``', the
    default one backtick is enough to enclose it.
    However, if the content is like '` var `` print ```',
    we have to use four backticks as delimiter.
    """
    backtick_groups: List[str] = PATT_BACKTICK.findall(node.text)

    backtick_group_lens = {
        len(group)
        for group in backtick_groups
    }

    numtick = minticks
    while numtick in backtick_group_lens:
        numtick += 1

    return '`' * numtick
