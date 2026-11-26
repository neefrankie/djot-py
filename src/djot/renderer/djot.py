import re
from typing import Callable, Dict, List, Sequence

from djot.common.string import (
    is_word_char_at_end,
)

from djot.ast import (
    Doc,
    AstNode,
    HasChildren,
    is_block,
    is_inline,
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

Handler = Callable[['DjotRenderer', AstNode], None]

class DjotRenderer:
    ESCAPE_PATTERN = re.compile(r"""([~`'"${}\[\]^<>\\*_|]|-(?=-)|!(?=\[)|\.(?=\.))""")
    HASH_PATTERN = re.compile(r'^#')

    def __init__(self, doc: Doc):
        self.doc = doc
        self.wrap_width = 0
        self.prefixes: List[str] = []
        self.buffer: List[str] = []
        self.start_of_line = True
        self.end_of_prefix = 0
        self.column = 0
        self.needs_blankline = False

        self.handlers: Dict[str, Handler] = {}

    def register_handler(self, name: str, handler: Handler):
        self.handlers[name] = handler

    def escape(self, s: str) -> str:
        s = self.ESCAPE_PATTERN.sub(r'\\\1', s)
        if self.column == 0 or self.column == self.end_of_prefix:
            s = self.HASH_PATTERN.sub(r'\\#', s)

        return s

    def out(self, s: str):
        self.lit(self.escape(s))

    def do_blank_lines(self):
        if self.needs_blankline:
            self.cr()
            self.newline()
            self.needs_blankline = False

    def lit(self, s: str):
        self.buffer.append(s)
        self.column += len(s)
        self.start_of_line = False

    def blankline(self):
        self.needs_blankline = True

    def newline(self):
        if self.end_of_prefix == self.column:
            
            i = len(self.buffer)
            while i > 0:
                s = self.buffer[i - 1]
                if not s.endswith(' ') and len(s) > 0:
                    break
                # ends with space or empty string.
                s = s.rstrip(' ')
                if s:
                    self.buffer[i - 1] = s
                    break
                else:
                    self.buffer.pop()
                    i -= 1

        self.end_of_prefix = 0
        self.column = 0
        self.buffer.append('\n')

        if self.prefixes:
            for p in self.prefixes:
                self.buffer.append(p)
                self.column += len(p)
            self.end_of_prefix = self.column

        self.start_of_line = True

    def cr(self):
        if not self.start_of_line:
            self.newline()

    def wrap(self):
        if self.wrap_width <= 0:
            return

        idx = len(self.buffer) - 1
        if (
            not self.start_of_line
            and len(self.buffer) > 0
            and self.column > self.wrap_width
        ):
            last_buff = ''
            while idx > 0:
                last_buff = self.buffer[idx]
                if last_buff == ' ':
                    break
                elif not last_buff.strip():
                    return
                idx -= 1
            if idx < 0:
                return

        if idx < len(self.buffer) - 1:
            execess_on_line = self.buffer[idx + 1:]
            if self.buffer[-1] == ' ':
                self.buffer.pop()

            self.newline()
            self.start_of_line = True

            for line in execess_on_line:
                self.buffer.append(line)
                self.column += len(line)
                self.start_of_line = False

    def space(self):
        self.wrap()
        self.lit(' ')

    def soft_break(self):
        if self.wrap_width >= 0:
            self.newline()
        else:
            self.space()

    def needs_braces(self, node: HasChildren[InlineNode]) -> bool:
        return (
            begins_with_whitespace(node)
            or ends_with_whitespace(node)
            or (
                len(self.buffer) > 0
                and is_word_char_at_end(self.buffer[-1])
            )
        )

    def no_wrap(self, action: Callable[[], None]):
        old_wrap_width = self.wrap_width
        self.wrap_width = -1
        action()
        self.wrap_width = old_wrap_width

    def inline_container(
        self,
        node: HasChildren[InlineNode],
        delim: str,
        needs_braces: bool | None = None
    ):
        needs_braces = needs_braces or self.needs_braces(node)
        if needs_braces:
            self.lit('{')
        self.lit(delim)
        self.render_children(node.children)
        self.lit(delim)
        if needs_braces:
            self.lit('}')

    def lit_lines(self, s: str):
        lns = s.splitlines()
        if lns[-1] == '':
            lns.pop()
        for ln in lns:
            self.lit(ln)
            self.cr()

    def verbatim_node(self, node: HasText):
        ticks = verbatim_delim(node, 1)
        self.lit(ticks)
        if node.text.startswith('`'):
            self.lit(' ')
        self.lit(node.text)
        if node.text.endswith('`'):
            self.lit(' ')
        self.lit(ticks)

    def render_children(self, children: Sequence[AstNode]):
        for child in children:
            self.render_node(child)

        if children and not is_block(children[0]):
            self.wrap()

    def render_node(self, node: AstNode):
        self.do_blank_lines()
        handler = self.handlers.get(node.tag, None)
        if handler:
            if (node.attributes and is_block(node)):
                self.render_attributes(node)
                self.cr()

            handler(self, node)

            if (node.attributes and is_inline(node)):
                self.render_attributes(node)

        else:
            raise Exception(f'No renderer defined  for node type {node.tag}')

    def render_attributes(self, node: AstNode):
        if not node .attributes:
            return

