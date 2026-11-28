from dataclasses import dataclass
import re
from typing import Callable, List, Sequence

from djot.common import Alignment
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
    HasText,
    InlineNode,
    is_block,
    is_inline,
    Para,
    ThematicBreak,
    Heading,
    Div,
    BulletList,
    OrderedList,
    TaskList,
    CheckboxStatus,
    DefinitionList,
    Term,
    Definition,
    Table,
    Row,
    BlockQuote,
    CodeBlock,
    RawBlock,
    Footnote,
    Reference,
    Str,
    SoftBreak,
    HardBreak,
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

        self.handlers = {
            'doc': self.render_doc,
            'footnote': self.render_footnote,
        }


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

            handler(node)

            if (node.attributes and is_inline(node)):
                self.render_attributes(node)

        else:
            raise Exception(f'No renderer defined  for node type {node.tag}')

        match node:
            case Doc():
                self.render_doc(node)
            case Footnote():
                self.render_footnote(node)
            case Reference():
                self.render_reference(node)
            case Para():
                self.render_para(node)
            case ThematicBreak():
                self.render_thematic_break()
            case Div():
                self.render_div(node)
            case Heading():
                self.render_heading(node)
            case BlockQuote():
                self.render_block_quote(node)
            case CodeBlock():
                self.render_code_block(node)
            case RawBlock():
                self.render_raw_block(node)
            case DefinitionList():
                self.render_definition_list(node)
            case OrderedList():
                self.render_ordered_list(node)
            case BulletList():
                self.render_bullet_list(node)
            case TaskList():
                self.render_task_list(node)
            case Term():
                self.render_term(node)
            case Definition():
                self.render_definition(node)
            case Table():
                self.render_table(node)
            case Str():
                self.render_str(node)
            case FootnoteReference():
                self.render_footnote_reference(node)
            case Symb():
                self.render_symb(node)
            case Email():
                self.render_email(node)
            case Url():
                self.render_url(node)
            case Span():
                self.render_span(node)
            case Link():
                self.render_link(node)
            case Image():
                self.render_image(node)
            case RawInline():
                self.render_raw_inline(node)
            case Verbatim():
                self.render_verbatim(node)
            case InlineMath():
                self.render_inline_math(node)
            case DisplayMath():
                self.render_display_math(node)

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

    def render_heading(self, node: Heading):
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
            self.lit(marker)
            self.needs_blankline = False
            self.space()
            self.prefixes.append(' ' * (len(marker) + 1))
            self.render_children(item.children)
            self.prefixes.pop()

        if not loose:
            self.blankline()

    def render_bullet_list(self, node: BulletList):
        items = node.children
        loose = node.loose

        for i, item in enumerate(items):
            if i > 0:
                self.cr()
                if loose:
                    self.newline()

            marker = node.style.value
            self.lit(marker)
            self.needs_blankline = False
            self.space()
            self.prefixes.append(' ' * (len(marker) + 1))
            self.render_children(item.children)
            self.prefixes.pop()

        if not loose:
            self.blankline()

    def render_task_list(self, node: TaskList):
        items = node.children
        loose = node.loose

        for i, item in enumerate(items):
            if i > 0:
                self.cr()
                if loose:
                    self.newline()

            self.needs_blankline = False
            check_marker = 'X' if item.checkbox == CheckboxStatus.CHECKED else ' '
            self.lit(f'- [{check_marker}]')
            self.space()
            self.prefixes.append(' ' * 6)
            self.render_children(item.children)
            self.prefixes.pop()

        if not loose:
            self.blankline()

    def render_term(self, node: Term):
        self.render_children(node.children)
        self.blankline()

    def render_definition(self, node: Definition):
        self.render_children(node.children)

    def render_separator(self, head_row: Row):
        for j, cell in enumerate(head_row.children):
            if j == 0:
                self.lit('|')

            match cell.align:
                case Alignment.LEFT:
                    self.lit(':--')
                case Alignment.RIGHT:
                    self.lit('--:')
                case Alignment.CENTER:
                    self.lit(':--:')
                case _:
                    self.lit('---')

            self.lit('|')

        self.cr()


    def render_table(self, node: Table):
        caption = node.caption
        rows = node.children

        for i, row in enumerate(rows):
            # If last row was head and this one is not, add separator line.
            if not row.head and i > 0 and rows[i-1].head:
                self.render_separator(rows[i-1])

            for j, cell in enumerate(row.children):
                if j == 0:
                    self.lit('|')
                self.no_wrap(lambda: self.render_children(cell.children))
                self.lit('|')

            self.cr()

        if rows and rows[-1].head:
            self.render_separator(rows[-1])

        if caption.children:
            self.newline()
            self.lit('^ ')
            self.needs_blankline = False
            self.prefixes.append('  ')
            self.render_children(caption.children)
            self.prefixes.pop()
            self.blankline()

        self.blankline()

    def render_str(self, node: Str):
        self.out(node.text)

    def render_space(self):
        self.space()

    def render_soft_break(self):
        self.soft_break()

    def render_smart_punctuation(self, node: SmartPunctuation):
        self.lit(node.text)

    def render_non_breaking_space(self):
        self.lit('\\')

    def render_single_quoted(self, node: SingleQuoted):
        self.inline_container(node, "'")

    def render_double_quoted(self, node: DoubleQuoted):
        self.inline_container(node, '"')

    def render_emph(self, node: Emph):
        self.inline_container(node, '_')

    def render_strong(self, node: Strong):
        self.inline_container(node, '*')

    def render_superscript(self, node: Superscript):
        self.inline_container(node, '^')

    def render_subscript(self, node: Subscript):
        self.inline_container(node, '~')

    def render_mark(self, node: Mark):
        self.inline_container(node, '=', True)

    def render_delete(self, node: Delete):
        self.inline_container(node, '-', True)

    def render_insert(self, node: Insert):
        self.inline_container(node, '+', True)

    def render_footnote_reference(self, node: FootnoteReference):
        self.lit(f'[^{node.text}]')

    def render_symb(self, node: Symb):
        self.lit(f':{node.alias}:')

    def render_email(self, node: Email):
        self.lit(f'<{node.text}>')

    def render_url(self, node: Url):
        self.lit(f'<{node.text}>')

    def render_span(self, node: Span):
        self.lit('[')
        self.render_children(node.children)
        self.lit(']')

    def render_link(self, node: Link):
        self.lit('[')
        self.render_children(node.children)
        self.lit(']')
        if node.reference:
            self.lit('[')
            if node.reference != get_string_content(node):
                self.lit(node.reference)
            self.lit(']')
        elif node.destination:
            self.lit('(')
            self.lit(node.destination)
            self.lit(')')
        else: # should not happen
            self.lit('()')

    def render_image(self, node: Image):
        self.lit('![')
        self.render_children(node.children)
        self.lit(']')
        if node.reference:
            self.lit('[')
            if node.reference != get_string_content(node):
                self.lit(node.reference)

            self.lit(']')

        elif node.destination:
            self.lit('(')
            self.lit(node.destination)
            self.lit(')')
        else: # should not happen
            self.lit('()')

    def render_raw_inline(self, node: RawInline):
        self.verbatim_node(node)
        self.lit('{=' + node.format + '}')

    def render_verbatim(self, node: Verbatim):
        self.verbatim_node(node)

    def render_inline_math(self, node: InlineMath):
        self.lit('$')
        self.verbatim_node(node)

    def render_display_math(self, node: DisplayMath):
        self.lit('$$')
        self.verbatim_node(node)

    


        





        


def render_djot(doc: Doc) -> str:
    return DjotRenderer(doc).render()


        

