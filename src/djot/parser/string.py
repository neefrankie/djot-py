from typing import Iterator

from djot.ast.base import AstNode, HasChildren, HasText
from djot.ast.inline import FootnoteReference, HardBreak, SoftBreak


def iter_string_content(node: AstNode) -> Iterator[str]:
    if isinstance(node, FootnoteReference):
        return
    
    if isinstance(node, HasText):
        yield node.text
    elif isinstance(node, (SoftBreak, HardBreak)):
        yield '\n'
    elif isinstance(node, HasChildren):
        for child in node.children:
            yield from iter_string_content(child)

def get_string_content(node: AstNode) -> str:
    return ''.join(iter_string_content(node))