from dataclasses import dataclass
import re
from typing import Callable, Dict, List, Sequence

from djot.common.string import (
    is_word_char_at_end,
)
from djot.common.list_number import (
    format_number
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

@dataclass(slots=True)
class DjotRenderOptions:
    wrap_width: int = 0
    """
    0 means no wrap but soft_breaks are breaks.
    -1 means no wrap and soft_breaks are spaces.
    >0 means wrap to width, with soft_breaks as spaces.
    """

class DjotRenderer:
    ESCAPE_PATTERN = re.compile(r"""([~`'"${}\[\]^<>\\*_|]|-(?=-)|!(?=\[)|\.(?=\.))""")
    HASH_PATTERN = re.compile(r'^#')

    def __init__(
        self,
        doc: Doc,
        options: DjotRenderOptions | None = None
    ):
        self.doc = doc

        self.wrap_width = options.wrap_width if options else 0
        # A stack of prefixes for each new line.
        self.prefixes: List[str] = []
        self.buffer: List[str] = []
        self.start_of_line = True
        self.end_of_prefix = 0
        # How many characters are written on the current line
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
            # remove spaces after prefix
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

        # Prefix at the front of new line.
        # For example, some elements requires
        # indentation.
        if self.prefixes:
            for s in self.prefixes:
                self.buffer.append(s)
                self.column += len(s)
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
            # Try to find a space to wrap
            # only when we are in the middle of a line.
            # and current column exceeds wrap_width.
            last_buff = ''
            while idx > 0:
                last_buff = self.buffer[idx]
                if last_buff == ' ': # wrap at space.
                    break
                elif not last_buff.strip():
                    return
                idx -= 1
            if idx < 0:
                return

        # If we actually found a space,
        # try to insert a newline at idx.
        if idx < len(self.buffer) - 1:
            execess_on_line = self.buffer[idx + 1:]
            if self.buffer[-1] == ' ':
                self.buffer.pop()

            # Insert a newline somewhere between
            # two segments
            self.newline()
            # Newline inserted, so turn we are at the start of a line.
            self.start_of_line = True

            for line in execess_on_line:
                self.buffer.append(line)
                self.column += len(line)
                # When there are content in a line, we are not at the start of a line.
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

        attr = node.attributes

        self.lit('{')

        is_first = True

        if is_block(node):
            self.prefixes.append(' ')

        for k, v in attr.items():
            if not is_first:
                self.space()

            match k:
                case 'id':
                    self.lit('#')
                    self.lit(v)
                case 'class':
                    classes = v.split()
                    for i, cls in enumerate(classes):
                        if i > 0:
                            self.space()
                        self.lit('.')
                        self.lit(cls)
                case _:
                    self.lit(k)
                    self.lit('="')
                    self.out(v)
                    self.lit('"')

            is_first = False

        if is_block(node):
            self.prefixes.pop()

        self.lit('}')

    def render(self) -> str:
        self.render_node(self.doc)
        return ''.join(self.buffer)


    def render_doc(self, node: Doc):
        self.render_children(node.children)
        self.prefixes = []
        self.cr()
        has_references = len(node.references) > 0
        if has_references:
            self.cr()
            self.newline()

        for ref in node.references.values():
            self.render_node(ref)

        has_footnotes = len(node.footnotes) > 0
        for footnote in node.footnotes.values():
            self.render_node(footnote)

        self.prefixes = []
        self.cr()

    def render_footnote(self, node: Footnote):
        self.lit('[^' + node.label + ']: ')
        self.space()
        self.needs_blankline = False
        self.prefixes.append(' ')
        self.render_children(node.children)
        self.prefixes.pop()
        self.blankline()

    def render_reference(self, node: Reference):
        self.lit('[')
        self.lit(node.label)
        self.lit(']:')
        self.prefixes.append('  ')
        self.space()
        self.lit(node.destination)
        self.wrap()
        self.prefixes.pop()
        self.blankline()

    def render_para(self, node: Para):
        self.render_children(node.children)
        self.blankline()

    def render_thematic_break(self):
        self.lit('* * * * *')
        self.blankline()

    def render_div(self, node: Div):
        self.lit(':::') # TODO: I want to keep a 'name' field.
        self.cr()
        self.render_children(node.children)
        self.cr()
        self.lit(':::')
        self.blankline()

    def reander_heading(self, node: Heading):
        hashes = '#' * node.level
        self.lit(hashes + ' ')
        self.prefixes.append(hashes + ' ')
        self.render_children(node.children)
        self.prefixes.pop()
        self.blankline()

    def render_block_quote(self, node: BlockQuote):
        self.prefixes.append('> ')
        self.lit('> ')
        self.render_children(node.children)
        self.prefixes.pop()
        self.blankline()

    def render_code_block(self, node: CodeBlock):
        ticks = verbatim_delim(node, 3)
        self.lit(ticks)
        if node.lang:
            self.lit(' ' + node.lang)

        self.cr()
        self.lit_lines(node.text)
        self.cr()
        self.lit_lines(ticks)
        self.blankline()

    def render_raw_block(self, node: RawBlock):
        ticks = verbatim_delim(node, 3)
        self.lit_lines(ticks)
        self.lit(' =' + node.format)
        self.cr()
        self.lit_lines(node.text)
        self.cr()
        self.lit(ticks)
        self.blankline()

    def render_definition_list(self, node: DefinitionList):
        items = node.children
        for i, item in enumerate(items):
            if i > 0:
                self.newline()
            self.lit(':')
            self.needs_blankline = False
            self.space()
            self.prefixes.append(' ' * 2)
            self.render_children((item.term, item.definition))
            self.prefixes.pop()

    def render_ordered_list(self, node: OrderedList):
        style = node.style
        start = node.start
        items = node.children
        loose = node.loose

        for i, item in enumerate(items):
            if i > 0:
                self.cr()
                if loose:
                    self.newline()

            marker = format_number(start + i, style)


        


def render_djot(doc: Doc) -> str:
    return DjotRenderer(doc).render()


        

