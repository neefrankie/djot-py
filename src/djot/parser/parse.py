from dataclasses import fields, is_dataclass
from typing import List, Set

from ..block import parse_events


from ..ast.base import (
    HasChildren,
    AstNode,
)
from ..ast.doc import Doc
from ..block import EventParser
from .builder import ASTBuidler

OMIT_FIELDS: Set[str] = {
    'children',
    'tag',
    'pos',
    'attributes'
    'auto_attributes',
    'references',
    'auto_references',
    'footnotes',
}

import json

def stringify(x: object) -> str:
    # 转为 JSON 字符串
    json_str = json.dumps(x, ensure_ascii=False)
    
    # 如果 JSON 字符串中真的出现了“反斜杠+真实换行符”的组合，
    # 把它替换为“反斜杠+字母n”（即 \n 的字面量）
    return json_str.replace("\\\n", "\\n")

def render_ast_node(
        node: AstNode, 
        buff: List[str],
        indent: int
    ):
    buff.append(' ' * indent)
    if indent > 128:
        buff.append("(((DEEPLY NESTED CONTENT OMITTED)))\n")
        return

    buff.append(node.tag)
    if node.pos:
        if node.pos:
            buff.append(f' ({node.pos.start.line}:{node.pos.start.col}:{node.pos.start.offset}-{node.pos.end.line}:{node.pos.end.col}:{node.pos.end.offset})')

    if is_dataclass(node):
        for field in fields(node):
            if field.name not in OMIT_FIELDS:
                v = getattr(node, field.name)
                if v is not None:
                    buff.append(f' {field.name}={stringify(v)}')

    if node.attributes:
        for k, v in node.attributes.items():
            buff.append(f' {k}={stringify(v)}')

    buff.append('\n')
    if isinstance(node, HasChildren) and node.children:
        for child in node.children:
            render_ast_node(child, buff, indent + 2)

def render_ast(doc: Doc) -> str:
    """
    Render an AST in human-readable form, with indentation
    showing the hierarchy.
    """
    buff: List[str] = []
    render_ast_node(doc, buff, 0)
    if len(doc.references) > 0:
        buff.append('references\n')
        for k, v in doc.references.items():
            buff.append(f'  [{stringify(k)}] =\n')
            render_ast_node(v, buff, 4)

    if len(doc.footnotes) > 0:
        buff.append('footnotes\n')
        for k, v in doc.footnotes.items():
            buff.append(f'  [{stringify(k)}] =\n')
            render_ast_node(v, buff, 4)

    return ''.join(buff)

def parse(input_: str) -> Doc:
    parser = parse_events(input_)
    parser = EventParser(input_)
    builder = ASTBuidler(
        parser.source_text,
        list(parser.parse())
    )
    return builder.build()