from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Callable, Dict, Iterator, List, NamedTuple

from .event import Event
from .options import Options, Warning
from .attributes import AttributeParser, ParseStatus
from .find import (
    find,
    FindResult
)
from .inline import InlineParser

_re_task_list_item = re.compile(r'^[+*-] \[[Xx ]\]')
# 1. ordered, decimal-enumerated, followed by period
# 1) ordered, decimal-enumerated, followed by parenthesis
# (1) ordered, decimal-enumerated, enclosed in parentheses
_re_decimal_item = re.compile(r'^[(]?[0-9]+[).]')
_re_decimal_multiple = re.compile(r'[0-9]+')
# a. ordered, lower-alpha-enumerated, followed by period
# a) ordered, lower-alpha-enumerated, followed by parenthesis
# (a) ordered, lower-alpha-enumerated, enclosed in parentheses
# i. 
# i)
# (i)
_re_lower_roman_alpha_item = re.compile(r'^[(]?[ivxlcdm][).]')
_re_lower_alpha_multiple = re.compile(r'[a-z]+')

# A. ordered, upper-alpha-enumerated, followed by period
# A) ordered, upper-alpha-enumerated, followed by parenthesis
# (A) ordered, upper-alpha-enumerated, enclosed in parentheses
# I. ordered, upper-roman-enumerated, followed by period
# I) ordered, upper-roman-enumerated, followed by parenthesis
# (I) ordered, upper-roman-enumerated, enclosed in parentheses
_re_upper_roman_alpha_item = re.compile(r'^[(]?[IVXLCDM][).]')
_re_upper_alpha = re.compile(r'[A-Z]+')

_re_lower_roman_item = re.compile(r'^[(]?[ivxlcdm]+[).]')
_re_upper_roman_item = re.compile(r'^[(]?[IVXLCDM]+[).]')

# a. 
# a) 
# (a) 
_re_lower_alpha_item = re.compile(r'^[(]?[a-z][).]')
_re_lower_alpha_single = re.compile(r'[a-z]')

# A. ordered, upper-alpha-enumerated, followed by period
# A) ordered, upper-alpha-enumerated, followed by parenthesis
# (A) ordered, upper-alpha-enumerated, enclosed in parentheses
_re_upper_alpha_item = re.compile(r'^[(]?[A-Z][).]')
_re_upper_alpha_single = re.compile(r'[A-Z]')

def get_list_styles(marker: str) -> List[str]:
    if marker == '+' or marker == '-' or marker == '*' or marker == ':':
        return [marker]
    elif _re_task_list_item.search(marker):
        return [marker[0] + "X"] # task list - include marker for consistency
    elif _re_decimal_item.search(marker):
        return [_re_decimal_multiple.sub('1', marker)]
    elif _re_lower_roman_alpha_item.search(marker):
        return [
            _re_lower_alpha_multiple.sub('i', marker),
            _re_lower_alpha_multiple.sub('a', marker)
        ]
    elif _re_upper_roman_alpha_item.search(marker):
        return [
            _re_upper_alpha.sub('I', marker),
            _re_upper_alpha.sub('A', marker)
        ]
    elif _re_lower_roman_item.search(marker):
        return [_re_lower_alpha_multiple.sub('i', marker)]
    elif _re_upper_roman_item.search(marker):
        return [_re_upper_alpha.sub('I', marker)]
    elif _re_lower_alpha_item.search(marker):
        return [_re_lower_alpha_single.sub('a', marker)]
    elif _re_upper_alpha_item.search(marker):
        return [_re_upper_alpha_single.sub('A', marker)]
    else:
        return []
    
def is_space_or_tab(cp: int) -> bool:
    return cp == 32 or cp == 9

def is_eol_char(cp: int) -> bool:
    return cp == 10 or cp == 13 # \n or \r

patt_endline = re.compile(r'[ \t]*\r?\n')
patt_word = re.compile(r'^\w+\s')
patt_whitespace = re.compile(r'[ \t\r\n]')
patt_non_whitespace = re.compile(r'[^ \t\r\n]+')
patt_blockquote_prefix = re.compile(r'[>][ \t\r\n]')
patt_bangs = re.compile(r'#+')
patt_code_fence = re.compile(r'(~~~~*|````*)([ \t]*)([^ \t\r\n`]*)[ \t]*\r?\n')
patt_row_sep = re.compile(r'(:?)--*(:?)([ \t]*\|[ \t]*)')
patt_next_bar_or_ticks = re.compile(r'[^`|\r\n]*(?:[|]|`+)')
patt_caption_start = re.compile(r'\^[ \t]+')
patt_footnote_start = re.compile(r'\[\^([^\]]+)\]:[ \t\r\n]')
patt_thematic_break = re.compile(r'[-*][ \t]*[-*][ \t]*[-*][-* \t]*\r?\n')
patt_div_fence = re.compile(r'(::::*)[ \t]*\r?\n')
patt_div_fence_start = re.compile(r'(::::*)[ \t]*')
patt_div_fence_end = re.compile(r'([\w_-]*)[ \t]*\r?\n')
# [anything]: 
# re.compile(r'\[([^\]\r\n]*)\]:([ \t]+[^ \t\r\n]*)?[\r\n]')
# [ followed by anything not ], \r or \n, followed by ], followed by :, followed by space,
# followed by optional non-space, with newline at end.
patt_reference_definition = re.compile(r'\[([^\]\r\n]*)\]:([ \t]+[^ \t\r\n]*|)[\r\n]')
patt_table_row = re.compile(r'(\|[^\r\n]*\|)[ \t]*\r?\n')
patt_list_marker = re.compile(
    r'(:?[-*+:]'
    r'|\([0-9]+\)'
    r'|[0-9]+[.)]'
    r'|[ivxlcdmIVXLCDM]+[.)]'
    r'|\([ivxlcdmIVXLCDM]+\)'
    r'|[a-zA-Z][.)]'
    r'|\([a-zA-Z]\)'
    r')'
    r'[ \t\r\n]'
)
patt_task_list_marker = re.compile(
    r'[*+-] \[[Xx ]\][ \t\r\n]'
)

class ContentType(Enum):
    None_ = 0
    Inline = 1
    Block = 2
    Text = 3
    Cells = 4
    Attributes = 5
    ListItem = 6

@dataclass
class BlockSpec:
    name: str
    type_: ContentType
    content: ContentType
    continue_fn: Callable[['Container'], bool]
    open_fn: Callable[['BlockSpec'], bool]
    close_fn: Callable[[], None]

class HeadingExtra(NamedTuple):
    level: int

class FootnoteExtra(NamedTuple):
    label: str
    indent: int

class RefDefExtra(NamedTuple):
    key: str
    indent: int

@dataclass
class ListExtra:
    styles: List[str]
    indent: int

class TableExtra(NamedTuple):
    columns: int

class FencedDivOpenExtra(NamedTuple):
    colons: int

class FencedDivEndExtra(NamedTuple):
    startpos: int
    endpos: int

class CodeBlockExtra(NamedTuple):
    close_pattern: re.Pattern

class Container:
    def __init__(self, spec: BlockSpec, extra: Dict[str, Any] | None = None):
        self.name: str = spec.name
        self.type = spec.type_
        self.content = spec.content
        self.continue_fn = spec.continue_fn
        self.close_fn = spec.close_fn
        self.indent = 0
        self.inline_parser: InlineParser | None = None
        self.attribute_parser: AttributeParser | None = None
        self.extra = extra or {}

        self.heading_extra: HeadingExtra | None = None
        self.footnote_extra: FootnoteExtra | None = None
        self.ref_def_extra: RefDefExtra | None = None
        self.list_extra: ListExtra | None = None
        self.table_extra: TableExtra | None = None
        self.fenced_div_open_extra: FencedDivOpenExtra | None = None
        self.fenced_div_end_extra: FencedDivEndExtra | None = None
        self.code_block_extra: CodeBlockExtra | None = None

    def with_heading(self, level: int) -> 'Container':
        self.heading_extra = HeadingExtra(
            level=level
        )
        return self
    
    def with_footnote(self, label: str, indent: int) -> 'Container':
        self.footnote_extra = FootnoteExtra(
            label=label,
            indent=indent
        )
        return self
    
    def with_reference_definition(self, key: str, indent: int) -> 'Container':
        self.ref_def_extra = RefDefExtra(
            key=key,
            indent=indent
        )
        return self
    
    def with_list(self, styles: List[str], indent: int) -> 'Container':
        self.list_extra = ListExtra(
            styles=styles,
            indent=indent
        )
        return self
    
    def with_table(self, columns: int) -> 'Container':
        self.table_extra = TableExtra(
            columns=columns
        )
        return self
    
    def with_fenced_div_open(self, colons: int) -> 'Container':
        self.fenced_div_open_extra = FencedDivOpenExtra(
            colons=colons
        )
        return self
    
    def with_fenced_div_end(
        self,
        startpos: int,
        endpos: int
    ) -> 'Container':
        self.fenced_div_end_extra = FencedDivEndExtra(
            startpos=startpos,
            endpos=endpos
        )
        return self
    
    def with_code_block(self, close_pattern: re.Pattern) -> 'Container':
        self.code_block_extra = CodeBlockExtra(
            close_pattern=close_pattern
        )
        return self
    


@dataclass
class ParseCellResult:
    startpos: int
    endpos: int
    matches: List[Event]


class EventParser:
    def __init__(self, subject: str, options: Options | None = None):
        if subject and subject[-1] != '\n':
            subject += '\n'
        self.subject = subject
        self.maxoffset = len(subject) - 1
        self.options = options or Options()
        self.warn = self.options.warn
        self.indent = 0
        self.startline = 0

        self.starteol = 0 # start position of end of line
        self.endeol = 0 # end position of end of line
        
        self.matches: List[Event] = []
        # In my opinion, this is just a dispatcher to use specific
        # groups of EventParser methods for different elements.
        self.containers: List[Container] = []
        self.pos = 0
        self.last_matched_container: int | None = 0
        self.finished_line = False
        self.returned = 0

        self.para_spec: BlockSpec = BlockSpec(
            name='para',
            type_=ContentType.Block,
            content=ContentType.Inline,
            continue_fn=self._continue_para,
            open_fn=self._open_para,
            close_fn=self._close_para,
        )

        self.specs: List[BlockSpec] = [
            BlockSpec(
                name='block_quote',
                type_=ContentType.Block,
                content=ContentType.Block,
                continue_fn=self._continue_block_quote,
                open_fn=self._open_block_quote,
                close_fn=self._close_block_quote,
            ),
            BlockSpec(
                name='heading',
                type_=ContentType.Block,
                content=ContentType.Inline,
                continue_fn=self._continue_heading,
                open_fn=self._open_heading,
                close_fn=self._close_heading
            ),
            BlockSpec(
                name='caption',
                type_=ContentType.Block,
                content=ContentType.Inline,
                continue_fn=self._continue_caption,
                open_fn=self._open_caption,
                close_fn=self._close_caption
            ),
            # should go before reference definitions
            BlockSpec(
                name='footnote',
                type_=ContentType.Block,
                content=ContentType.Block,
                continue_fn=self._continue_footnote,
                open_fn=self._open_footnote,
                close_fn=self._close_footnote,
            ),
            BlockSpec(
                name='reference_definition',
                type_=ContentType.Block,
                content=ContentType.None_,
                continue_fn=self._continue_reference_definition,
                open_fn=self._open_reference_definition,
                close_fn=self._close_reference_definition,
            ),
            BlockSpec(
                name='thematic_break',
                type_=ContentType.Block,
                content=ContentType.None_,
                continue_fn=self._continue_thematic_break,
                open_fn=self._open_thematic_break,
                close_fn=self._close_thematic_break
            ),
            BlockSpec(
                name='list',
                type_=ContentType.Block,
                content=ContentType.ListItem,
                continue_fn=self._continue_list,
                open_fn=self._open_list,
                close_fn=self._close_list
            ),
            BlockSpec(
                name='list_item',
                type_=ContentType.ListItem,
                content=ContentType.Block,
                continue_fn=self._continue_list_item,
                open_fn=self._open_list_item,
                close_fn=self._close_list_item,
            ),
            BlockSpec(
                name='table',
                type_=ContentType.Block,
                content=ContentType.Cells,
                continue_fn=self._continue_table,
                open_fn=self._open_table,
                close_fn=self._close_table,
            ),
            BlockSpec(
                name='attributes',
                type_=ContentType.Block,
                content=ContentType.Attributes,
                open_fn=self._open_attributes,
                continue_fn=self._continue_attributes,
                close_fn=self._close_attributes,
            ),
            BlockSpec(
                name='fenced_div',
                type_=ContentType.Block,
                content=ContentType.Block,
                continue_fn=self._continue_fenced_div,
                open_fn=self._open_fenced_div,
                close_fn=self._close_fenced_div,
            ),
            BlockSpec(
                name='code_block',
                type_=ContentType.Block,
                content=ContentType.Text,
                continue_fn=self._continue_code_block,
                open_fn=self._open_code_block,
                close_fn=self._close_code_block,
            ),
        ]

    def _open_para(self, spec: BlockSpec) -> bool:
        self.add_container(Container(spec, {}))
        self.add_match(self.pos, self.pos, '+para')
        return True
    
    def _continue_para(self, container: Container) -> bool:
        # any [ \t\r\n]
        # For paragraph, newlines are treated as soft breaks and
        # interpreted like spaces in formatted output.
        if self.find(patt_whitespace) is None:
            return True
        else:
            return False
        
    def _close_para(self):
        # A paragraph ends with a blank line or the end of document.
        # Appends parsed inline elements.
        self.get_inline_matches()
        self.containers.pop()
        last = self.matches[-1]
        # TODO: which symbol is it pointing to now?
        ep = (last and last.endpos + 1) or self.pos
        self.add_match(ep, ep, '-para')

    def _open_block_quote(self, spec: BlockSpec) -> bool:
        """
        A block quote is a sequence of lines, each of which begins with >,
        followed either by a space or by the end of the line.
        The contents of the block quote (minus initial >) are parsed as
        block-level content.
        """
        # [>][ \t\r\n]
        if self.find(patt_blockquote_prefix):
            self.add_container(Container(spec))
            self.add_match(self.pos, self.pos, '+block_quote')
            self.pos += 1 # first non-space char.
            return True
        else:
            return False
        
    def _continue_block_quote(self, container: Container) -> bool:
        if self.find(patt_blockquote_prefix):
            self.pos += 1 # first non-space char.
            return True
        else:
            return False
        
    def _close_block_quote(self):
        self.containers.pop()
        self.add_match(self.pos, self.pos, '-block_quote')

    def _open_heading(self, spec: BlockSpec) -> bool:
        """
        A heading starts with a sequence of one or more # characters,
        followed by whitespace.
        The number of characters defines the heading level.
        The heading text may spill over onto following lines,
        which may also be preceded by the same number of # characters.
        """
        # `#+`
        m = self.find(patt_bangs) # stops at last #
        # space after #
        if m and find(self.subject, patt_whitespace, m.endpos+1): # only a single whitespace
            level = m.endpos - m.startpos + 1
            self.add_container(Container(spec).with_heading(level))
            self.add_match(m.startpos, m.endpos, '+heading') # The #+ chars
            self.pos = m.endpos + 1 # after last #
            return True
        else:
            return False
        
    def _continue_heading(self, container: Container):
        # search `#+`
        m = self.find(patt_bangs)
        if (m and 
            container.heading_extra and 
            container.heading_extra.level == (m.endpos - m.startpos + 1) and
            find(self.subject, patt_whitespace, m.endpos + 1)):
            return True
        else:
            return False
        
    def _close_heading(self):
        self.get_inline_matches()
        self.containers.pop()
        last = self.matches[-1]
        # TODO: figure out what symbol is being pointed to. 
        ep = (last and last.endpos + 1) or self.pos
        self.add_match(ep, ep, '-heading')

    def _open_caption(self, spec: BlockSpec) -> bool:
        """
        Attach a caption to a table usiing ^.
        It can contain inline formatting, and can extend over multiple lines,
        provinding they are indented relative to the ^
        """
        # '\^[ \t]+'
        m = self.find(patt_caption_start)
        if m:
            self.pos = m.endpos + 1 # first char after space.
            self.add_container(Container(spec)) # create inline parser
            self.add_match(self.pos, self.pos, '+caption') # ^
            return True
        else:
            return False
        
    def _continue_caption(self, container: Container) -> bool:
        # Returns true if no space is found.
        return find(self.subject, patt_whitespace, self.pos) is None
        
    def _close_caption(self):
        self.get_inline_matches()
        self.containers.pop()
        # TODO: why minus one?
        self.add_match(self.pos-1, self.pos-1, '-caption')

    def _open_footnote(self, spec: BlockSpec) -> bool:
        """
        A footnote consists of a footnote reference followed
        by a colon followed by the contents of the note,
        indented to any column beyond column in which
        the reference starts.
        The contents of the note are parsed as block-level content.

        [^foo]: This is a note
          with two paragraphs.

          Second paragraph.

          > a block quote in the note.
        """
        # type Block
        # content Block
        # \[\^([^\]]+)\]:[ \t\r\n]
        m = self.find(patt_footnote_start)
        if m:
            sp = m.startpos
            ep = m.endpos
            label = m.captures[0]
            self.add_container(
                Container(spec).with_footnote(
                    label=label,
                    indent=self.indent, # indent of current line
                )
            )
            self.add_match(sp, sp, '+footnote') # [
            self.add_match(sp + 2, ep - 3, 'note_label') # foo
            self.pos = ep # move to first space
            return True
        else:
            return False

    def _continue_footnote(self, container: Container):
        if not container.footnote_extra:
            return False
        if self.indent > container.footnote_extra.indent or self.pos == self.starteol:
            return True
        else:
            return False
        
    def _close_footnote(self):
        self.containers.pop()
        self.add_match(self.pos, self.pos, '-footnote')


    def _open_reference_definition(self, spec: BlockSpec) -> bool:
        """
        A reference definition consists of the reference label in square brackets,
        followed by a colon, followed by whitespace (or a newline) and the URL.
        The URL may be split over multiple lines (in which case teh lines will be concatenated,
        with any leading or trailing space removed).
        None of the chunks of the URL may contain internal whitespace.

        [foo]: http://example.com
        """
        # \[([^\]\r\n]*)\]:([ \t]+[^ \t\r\n]*|)[\r\n]
        m = self.find(patt_reference_definition)
        if m:
            label = m.captures[0] # anything inside []
            value = m.captures[1].lstrip() # anything after :
            self.add_container(
                Container(
                    spec
                ).with_reference_definition(
                    key=label,
                    indent=self.indent
                )
            )
            self.add_match(
                m.startpos,
                m.startpos,
                '+reference_definition'
            ) # [
            self.add_match(
                m.startpos,
                m.startpos + len(label) + 1,
                'reference_key'
            ) # foo
            if len(value) > 0:
                self.add_match(
                    self.starteol - len(value), # start position of value
                    self.starteol - 1, # end position of value
                    'reference_value'
                ) # http://example.com
            self.pos = self.starteol - 1 # before \n
            return True
        else:
            return False
        
    def _continue_reference_definition(self, container: Container) -> bool:
        if not container.ref_def_extra:
            return False
        if container.ref_def_extra.indent >= self.indent: # previous line was indented less than this line
            return False

        # [^ \t\r\n]+
        # Find URL split over multiple lines.
        nws = self.find(patt_non_whitespace)
        # Current position should not exceed the end of the line,
        # and content should be ended with a newline.
        if self.pos < self.starteol and nws and nws.endpos == self.starteol - 1:
            self.add_match(self.pos, self.starteol - 1, 'reference_value') # continuation of reference value
            self.pos = self.starteol # \n
            return True
        else:
            return False
        
    def _close_reference_definition(self):
        self.containers.pop()
        self.add_match(self.pos, self.pos, 'reference_definition')
    
    def _open_thematic_break(self, spec: BlockSpec) -> bool:
        """
        A line containing thre oor more * or - characters, and nothing else
        (except spaces or tabs) is treated as a thematic break. (<hr> in HTML)
        A thematic break may e indented.

        Then they went to sleep
            
            * * * *

        When they woke up, ...
        """
        # [-*][ \t]*[-*][ \t]*[-*][-* \t]*\r?\n
        # - * * also works for this regex.
        m = self.find(patt_thematic_break)
        if m:
            self.add_container(Container(spec))
            self.add_match(m.startpos, m.endpos, 'thematic_break')
            self.pos = m.endpos # \n
            return True
        else:
            return False
    
    def _continue_thematic_break(self, container: Container) -> bool:
        return False
        
    def _close_thematic_break(self):
        self.containers.pop()

    def _open_list(self, spec: BlockSpec) -> bool:
        r"""
        A list is simply a sequence of list items of the same type.
        Changing ordered list style or bullet will stop one list and start a new one.

        r'(:?[-*+:]' # :-, :*, :+, ::, -, *, +, :
        r'|\([0-9]+\)' # (1)
        r'|[0-9]+[.)]' # 1., 1)
        r'|[ivxlcdmIVXLCDM]+[.)]' # i., i), I., I)
        r'|\([ivxlcdmIVXLCDM]+\)' # (i), (I)
        r'|[a-zA-Z][.)]' # a., a), A., A)
        r'|\([a-zA-Z]\)' # (a), (A)
        r')'
        r'[ \t\r\n]'
        """
        m = self.find(patt_list_marker)
        if m is None:
            return False
        sp = m.startpos
        ep = m.endpos # whitespace
        marker = self.subject[sp:ep]

        # A bullete list item that begins with [ ], [X] or [x]
        # followed by a space is a task list item.
        # [*+-] \[[Xx ]\][ \t\r\n]
        # * [ ] 
        mtask = self.find(patt_task_list_marker)
        if mtask is not None:
            marker = self.subject[mtask.startpos:mtask.startpos + 5] # * [X]

        # ['+'], ['-'], ['*'], [':']
        # ['-X']
        # ['(1)'], ['1.'], ['1)']
        # ['(i)', '(a)'], ['i.', 'a.'], ['i)', 'a)']
        # ['(I)', '(A)'], ['I.', 'A.'], ['I)', 'A)']
        # ['(i)'], ['i.'], ['i)']
        # ['(I)'], ['I.'], ['I)']
        # ['(a)'], ['a.'], ['a)']
        # ['(A)'], ['A.'], ['A)']
        styles = get_list_styles(marker)
        if len(styles) == 0:
            return False
        
        # adding container will close others
        self.add_container(
            Container(
                spec
            ).with_list(
                styles=styles,
                indent=self.indent,
            )
        )
        annot = '+list'
        for style in styles:
            annot = annot + '|' + style # +list|(1)
        self.add_match(sp, ep-1, annot) # (1), 1), etc.
        return True

    def _continue_list(self, container: Container) -> bool:
        if container.list_extra is None:
            return False
        
        if (self.indent > container.list_extra.indent) or (self.pos == self.starteol):
            return True
        else:
            m = self.find(patt_list_marker)
            if m is None:
                return False
            marker = self.subject[m.startpos:m.endpos]
            mtask = self.find(patt_task_list_marker)
            if mtask is not None:
                marker = self.subject[mtask.startpos:mtask.startpos + 5]

            styles = get_list_styles(marker)
            
            newstyles: List[str] = []
            for prev_style in container.list_extra.styles:
                if prev_style in styles:
                    newstyles.append(prev_style)

            if len(newstyles) > 0:
                container.list_extra.styles = newstyles
                return True
            
        return False
    
    def _close_list(self):
        self.containers.pop()
        self.add_match(self.pos, self.pos, '-list')

    def _open_list_item(self, spec: BlockSpec) -> bool:
        """
        A list item consists of a list marker, followed by a space (or a newline)
        followed by one or more lines, indented relative to the list marker.
        """
        m = self.find(patt_list_marker)
        if m is None:
            return False
        
        sp = m.startpos
        ep = m.endpos
        marker = self.subject[sp:ep]
        checkbox = None

        mtask = self.find(patt_task_list_marker)
        if mtask is not None:
            marker = self.subject[mtask.startpos:mtask.endpos+5]
            checkbox = self.subject[mtask.startpos+3:mtask.startpos+4]

        styles = get_list_styles(marker)
        if len(styles) == 0:
            return False

        # adding container will close others
        self.add_container(Container(spec).with_list(
            styles=styles,
            indent=self.indent,
        ))
        annot = '+list_item'
        for style in styles:
            annot = annot + '|' + style
        self.add_match(sp, ep-1, annot)
        self.pos = ep

        if checkbox:
            if checkbox == ' ':
                self.add_match(sp+2, sp+4, 'checkbox_unchecked')
            else:
                self.add_match(sp+2, sp+4, 'checkbox_checked')
            self.pos = sp+5

        return True
    
    def _continue_list_item(self, container: Container) -> bool:
        if container.list_extra is None:
            return False
        return self.indent > container.list_extra.indent or self.pos == self.starteol
    
    def _close_list_item(self):
        self.containers.pop()
        self.add_match(self.pos-1, self.pos-1, '-list_item')

    def _open_table(self, spec: BlockSpec) -> bool:
        """
        A pipe table consists of a sequence of rows.
        Each row starts and ends with a pipe character | and
        contains one or more cells separated by pipe characters.
        | fruit  | price |
        |--------|------:|
        | apple  |  4    |
        | banana |  10   |
        """
        # (\|[^\r\n]*\|)[ \t]*\r?\n
        # Match the whole line.
        m = self.find(patt_table_row)
        if m:
            self.add_container(Container(spec).with_table(columns=0))
            rawrow = m.captures[0] # | fruit  | price |
            self.add_match(m.startpos, m.startpos, '+table') # |
            if self.parse_table_row(m.startpos, m.startpos + len(rawrow) - 1):
                return True
            else:
                self.matches.pop() # what is it?
                self.containers.pop() # the container just addded
                return False
        else:
            return False
        
    def _continue_table(self, container: Container) -> bool:
        m = self.find(patt_table_row)
        if m:
            rawrow = m.captures[0]
            return self.parse_table_row(m.startpos, m.startpos + len(rawrow) - 1)
        else:
            return False
        
    def _close_table(self):
        self.containers.pop()
        self.add_match(self.pos, self.pos, '-table')
        
    def _open_attributes(self, spec: BlockSpec) -> bool:
        if ord(self.subject[self.pos]) == 123: # {
            attribute_parser = AttributeParser(self.subject)
            res = attribute_parser.feed(self.pos, self.starteol)
            if res.is_fail():
                return False
            elif res.is_done() and find(self.subject, patt_endline, res.position + 1) is None:
                return False
            else:
                container = self.add_container(Container(spec, {
                    'status': res.status,
                    'indent': self.indent,
                    'startpos': self.pos,
                    'slices': []
                }))
                container.attribute_parser = attribute_parser
                container.extra['slices'] = [
                    {'startpos': self.pos, 'endpos': self.starteol}
                ]
                self.pos = self.starteol
                return True
        else:
            return False
        
    def _continue_attributes(self, container: Container) -> bool:
        if container.extra['status'] == ParseStatus.DONE:
            return False
        if container.attribute_parser and self.indent > container.extra['indent']:
            container.extra['slices'].append({
                'startpos': self.pos,
                'endpos': self.starteol
            })
            res = container.attribute_parser.feed(self.pos, self.endeol)
            container.extra['status'] = res.status
            if res.status != ParseStatus.FAIL or find(self.subject, patt_endline, res.position + 1):
                self.pos = self.starteol
                return True
        self.add_match(container.extra['startpos'], container.extra['startpos'], '+para')
        attr_container = self.containers.pop()
        para = self.add_container(Container(self.para_spec, {}))
        if not para.inline_parser or not attr_container:
            raise ValueError('Missing inline_parser or attr_container')
        para.inline_parser.attribute_slices = attr_container.extra['slices']
        para.inline_parser.reparse_attributes()
        self.pos = para.inline_parser.lastpos + 1
        return True
    
    def _close_attributes(self):
        container = self.containers.pop()
        if not self.containers:
            return
        if container.extra['status'] == ParseStatus.CONTINUE:
            self.add_match(
                container.extra['startpos'],
                container.extra['startpos'],
                '+para'
            )
            para = self.add_container(Container(self.para_spec, {}), True)
            if not para or not para.inline_parser:
                raise ValueError('Cound not add paragraph')
            para.inline_parser.attribute_slices = container.extra['slices']
            para.inline_parser.reparse_attributes()
        else:
            self.add_match(
                container.extra['startpos'],
                container.extra['startpos'],
                '+block_attributes'
            )
            if container.attribute_parser:
                attr_matches = container.attribute_parser.matches
                for m in attr_matches:
                    self.matches.append(m)

            self.add_match(self.pos, self.pos, '-block_attributes')

    def _open_fenced_div(self, spec: BlockSpec) -> bool:
        """
        A div begins with a line of three or more colons,
        optionally followed by white space and a class name
        (but nothing else).
        It ends with a line of consecutive colons at least
        as long as the opening fence, or with the end of the document
        or containing block.
        The contents of a div are interpreted as block-level content.

        ::: waning
        Here is a paragraph.

        And here is another.
        :::
        """
        # (::::*)[ \t]*
        m = self.find(patt_div_fence_start) # ::: 
        if not m:
            return False
        colons = m.captures[0]
        # ([\w_-]*)[ \t]*\r?\n
        m2 = find(self.subject, patt_div_fence_end, m.endpos + 1) # content after starting :::
        if not m2:
            return False
        clsp = m2.startpos # class start
        lang = m2.captures[0] # class name
        self.add_container(
            Container(spec).with_fenced_div_open(colons=len(colons))
        )
        self.add_match(m.startpos, m.endpos, '+div')
        if len(lang) > 0:
            self.add_match(clsp, clsp + len(lang) - 1, 'class')
        self.pos = m2.endpos + 1 # after \n
        self.finished_line = True # stop recursion and content is treated as oridinary text.
        return True
    
    def _continue_fenced_div(self, container: Container) -> bool:
        tip = self.tip()
        if tip and tip.name == 'code_block': # in code block?
            return True # see #109
        # (::::*)[ \t]*\r?\n
        m = self.find(patt_div_fence)
        if m and container.fenced_div_open_extra and container.fenced_div_open_extra.colons:
            colons = m.captures[0] # :::
            if len(colons) >= container.fenced_div_open_extra.colons:
                container.with_fenced_div_end(
                    startpos=m.startpos,
                    endpos=m.startpos + len(colons) - 1
                )
                self.pos = m.endpos # \n
                return False
            
        return True
    
    def _close_fenced_div(self):
        container = self.containers.pop()
        if not container:
            return
        sp = container.fenced_div_end_extra.startpos if container.fenced_div_end_extra else self.pos

        ep = container.fenced_div_end_extra.endpos if container.fenced_div_end_extra else self.pos

        self.add_match(sp, ep, '-div')
        if sp == ep:
            self.warn(Warning('Unclosed div', self.pos))
    
    def _open_code_block(self, spec: BlockSpec) -> bool:
        # (~~~~*|````*)([ \t]*)([^ \t\r\n`]*)[ \t]*\r?\n
        m = self.find(patt_code_fence)
        if m:
            border = m.captures[0] # ~~~~ or ````
            ws = m.captures[1] # whitespace
            lang = m.captures[2]
            is_raw = lang.startswith('=')
            # (````*)[ \t]*\r?\n
            close_pattern = re.compile(r'(' + border + border[0:1] + r'*)' + r'[ \t]*[\r\n]')
            cont = self.add_container(
                Container(spec).with_code_block(
                    close_pattern=close_pattern,
                )
            )
            cont.indent = self.indent # remembe current line indent.
            self.add_match(
                m.startpos,
                m.startpos + len(border) - 1,
                '+code_block'
            ) # ~~~ or ```
            if len(lang) > 0:
                langstart = m.startpos + len(border) + len(ws)
                if is_raw:
                    self.add_match(
                        langstart,
                        langstart + len(lang) - 1,
                        'raw_format'
                    ) # Example: =html
                else:
                    self.add_match(
                        langstart,
                        langstart + len(lang) - 1,
                        'code_language'
                    ) # Example: python
                
            self.pos = m.endpos # \n
            self.finished_line = True
            return True
        else:
            return False
        
    def _continue_code_block(self, container: Container) -> bool:
        if not container.code_block_extra:
            return False
        # (````*)[ \t]*\r?\n
        m = self.find(container.code_block_extra.close_pattern)
        if m:
            container.with_fenced_div_end(
                startpos=m.startpos,
                endpos=m.startpos + len(m.captures[0]) - 1
            )
            self.pos = m.endpos # \n
            self.finished_line = True
            return True
        else:
            return False
        
    def _close_code_block(self):
        container = self.containers.pop()
        if not container:
            return

        sp = container.fenced_div_end_extra.startpos if container.fenced_div_end_extra else self.pos

        ep = container.fenced_div_end_extra.endpos if container.fenced_div_end_extra else self.pos

        self.add_match(sp, ep, '-code_block')
        if sp == ep:
            self.warn(Warning('Unclose code block', self.pos))

    def find(self, patt: re.Pattern) -> FindResult | None:
        return find(self.subject, patt, self.pos)
    
    def tip(self) -> Container | None:
        return self.containers[-1] if self.containers else None

    def add_match(self, startpos: int, endpos: int, annot: str):
        self.matches.append(Event(
            startpos=min(startpos, self.maxoffset),
            endpos=max(endpos, self.maxoffset),
            annot=annot,
        ))

    def get_inline_matches(self):
        # Transfer inline matches.
        container = self.tip()
        if container is None:
            return
        
        ilparser = container.inline_parser
        if ilparser is None:
            return

        last: Event | None = None # last appended.

        # Append inline matches.
        for m in ilparser.get_matches():
            # Join adjacent strings into a single match.
            if last and last.annot == 'str' and m.annot == 'str' and m.startpos == last.endpos + 1:
                self.matches[-1].endpos = m.endpos
            else:
                self.matches.append(m)

            last = m

    def close_unmatched_containers(self):
        last_matched = self.last_matched_container
        if last_matched is None:
            return
        tip = self.tip()
        while tip and last_matched < (len(self.containers) - 1):
            tip.close_fn()
            tip = self.tip()

    def add_container(self, container: Container, skip_close_unmatched: bool = False):
        if not skip_close_unmatched:
            self.close_unmatched_containers()

        tip = self.tip()
        # Only block_quote, footnote, and fenced_div's
        # content matches current container.
        while tip and tip.content != container.type:
            tip.close_fn()
            tip = self.tip()

        
        if container.content == ContentType.Inline:
            container.inline_parser = InlineParser(
                subject=self.subject,
                options=self.options, # TODO: how to mimic the js funcitonal implementation?
            )

        self.containers.append(container)
        return container
    
    # move parser position to first nonspace, adjusting indent.
    def skip_space(self):
        newpos = self.pos
        while is_space_or_tab(ord(self.subject[newpos])):
            newpos += 1

        self.indent = newpos - self.startline
        self.pos = newpos
    
    # set this.starteol, this endeol
    def get_eol(self):
        i = self.pos
        while not is_eol_char(ord(self.subject[i])):
            i += 1

        self.starteol = i
        # \r\n
        if ord(self.subject[i]) == 13 and ord(self.subject[i+1]) == 10:
            self.endeol = i + 1
        else: # \n
            self.endeol = i

    def parse_table_cell(self) -> ParseCellResult | None:
        inline_parser = InlineParser(
            subject=self.subject,
            options=self.options,
        )
        cell_complete = False
        sp = self.pos - 1 # we start on char after |
        ep = sp
        self.skip_space()
        while not cell_complete:
            m = self.find(patt_next_bar_or_ticks)
            if m is None:
                cell_complete = True
                break
            else: # we matched a | or `+
                nextbar = m.endpos
                if self.subject[nextbar] == '`' or inline_parser.in_verbatim():
                    inline_parser.feed(self.pos, nextbar)
                elif self.subject[nextbar-1] == '\\': # escaped |
                    inline_parser.feed(self.pos, nextbar)
                else:
                    inline_parser.feed(self.pos, nextbar - 1)
                    ep = nextbar
                    cell_complete = True

                self.pos = nextbar + 1

        if cell_complete:
            cell_matches = inline_parser.get_matches()
            return ParseCellResult(
                startpos=sp,
                endpos=ep,
                matches=cell_matches,
            )
        else:
            return None
        
    def parse_table_row(self, sp: int, ep: int) -> bool:
        # | fruit  | price |
        orig_matches = len(self.matches) # so we can rewind
        startpos = self.pos
        self.add_match(sp, sp, '+row') # |
        self.pos += 1

        # check to see if we have a separator line
        seps: List[Event] = []
        p = self.pos
        sepfound = False
        
        # |--------|------:|
        while not sepfound:
            # (:?)--*(:?)([ \t]*\|[ \t]*)
            m = find(self.subject, patt_row_sep, p)
            if m:
                left = m.captures[0] # optional :
                right = m.captures[1] # optional :
                trailing = m.captures[2] # |
                st = 'separator_default'
                if len(left) > 0 and len(right) > 0:
                    st = 'separator_center'
                elif len(right) > 0:
                    st = 'separator_right'
                elif len(left) > 0:
                    st = 'separator_left'

                seps.append(Event(
                    startpos=m.startpos,
                    endpos=m.endpos - len(trailing),
                    annot=st,
                ))

                p = m.endpos + 1
                if p == self.starteol:
                    sepfound = True
                    break
            else:
                break
        # end while

        if sepfound:
            for m in seps:
                self.add_match(m.startpos, m.endpos, m.annot)

            self.add_match(self.starteol - 1, self.starteol - 1, '-row')
            self.pos = self.starteol
            self.finished_line = True
            return True
        
        # if we get here, we're parsing a regular row.
        # | fruit  | price |
        while self.pos <= ep:
            cell = self.parse_table_cell()
            if cell is not None:
                self.add_match(cell.startpos, cell.endpos, '+cell')
                cell_matches = cell.matches
                for i, m in enumerate(cell_matches):
                    s = m.startpos
                    e = m.endpos

                    # last cell
                    if i == len(cell_matches) - 1 and m.annot == 'str':
                        # strip trailing space
                        while ord(self.subject[e]) == 32 and e >= s:
                            e = e - 1

                    self.add_match(s, e, m.annot)
            else:
                # rewind, this is not a valid table row
                self.pos = startpos
                while len(self.matches) > orig_matches:
                    self.matches.pop()
                
                return False
        
        # if we get here, we've parsed a table row.
        self.add_match(self.pos, self.pos, '-row')
        self.pos = self.starteol
        self.finished_line = True

        return True
    
    def __iter__(self) -> Iterator[Event]:
        while self.pos < len(self.subject):
            while len(self.matches) > 0 and self.returned < len(self.matches):
                self.returned = self.returned + 1
                yield self.matches[self.returned - 1]

            self.indent = 0
            self.startline = self.pos
            self.finished_line = False
            self.get_eol()

            # check open container for continuation
            self.last_matched_container = None
            idx = 0
            # If there are already open container, check if current line is continuation of it.
            while idx < len(self.containers):
                container = self.containers[idx]
                self.skip_space()
                if container.continue_fn(container):
                    self.last_matched_container = idx # latest container matching current line.
                else:
                    break
                idx += 1

            # if we hit a close fence, we can move to next line.
            if self.finished_line:
                matched_idx = self.last_matched_container if self.last_matched_container is not None else -1
                while self.containers and matched_idx < (len(self.containers) - 1):
                    tip = self.tip()
                    if tip:
                        tip.close_fn()

            if not self.finished_line:
                self.skip_space()
                is_blank = self.pos == self.starteol
                new_starts = False
                
                # If self.last_matched_container is not modified in the above while loop,
                # it remains -1.
                # In JS, self.containers[-1] returned undefined since 
                # JavaScript treats -1 as a property key, not an index, 
                # and returns undefined unless explicitly defined
                last_match = self.containers[self.last_matched_container] if self.containers and self.last_matched_container is not None else None

                # If current position is not start of end of line,
                # and haven't found a starting word,
                # and if last match exists, its content must be block or list_item.
                check_starts = not is_blank and (
                    (not last_match) or
                    (last_match.content == ContentType.Block) or
                    (last_match.content == ContentType.ListItem)
                ) and not self.find(patt_word)

                # This is essentially a manual recursion.
                # self.containers is recursion's stack.
                while check_starts:
                    check_starts = False
                    for spec in self.specs: # find a parser for current element.
                        # Only find a block parser, or if a block parser already exists,
                        # its content type must match current element's type, like list and list_item.
                        if ((not last_match and spec.type_ == ContentType.Block) or
                            (last_match and last_match.content == spec.type_)):
                            if spec.open_fn(spec): # now we find a parser for current element.
                                tip = self.tip() # it should be be the parser we just added.
                                if tip:
                                    self.last_matched_container = len(self.containers) - 1
                                    last_match = self.containers[self.last_matched_container]
                                    if self.finished_line:
                                        check_starts = False # stop recursion for fenced div and code block opening tag.
                                    else:
                                        self.skip_space() # now we calculuated indent.
                                        new_starts = True
                                        # If content is block or list_item, recurse.
                                        # Such elements include block_quote, footnote, list, list_item, fenced_div.
                                        check_starts = (
                                            spec.content == ContentType.Block or
                                            spec.content == ContentType.ListItem
                                        )
                                else:
                                    raise ValueError('No tip after opening container')
                                break # as soon as we find a parser, we can stop.
                # end while

                if not self.finished_line:
                    # handle remaining content
                    self.skip_space()

                    is_blank = (self.pos == self.starteol)
                    tip = self.tip()
                    is_lazy = (not is_blank and 
                               not new_starts and
                               self.last_matched_container is not None and
                               self.last_matched_container < len(self.containers) - 1 and 
                               tip and 
                               tip.content == ContentType.Inline)
                    
                    if not is_lazy:
                        # containers between last matched and tip()
                        self.close_unmatched_containers()

                    tip = self.tip()

                    # add para by default if there's text.
                    if not tip or tip.content == ContentType.Block:
                        if is_blank:
                            if not new_starts:
                                self.add_match(self.pos, self.endeol, 'blankline')
                        else:
                            self.para_spec.open_fn(self.para_spec)
                            tip = self.tip()
                            if tip:
                                tip.inline_parser = InlineParser(self.subject, self.options)

                    if tip and tip.content == ContentType.Text:
                        startpos = self.pos
                        if tip.indent is not None and self.indent > tip.indent:
                            # get back teh leading spaces we globbed
                            startpos = startpos - (self.indent - tip.indent)

                        self.add_match(startpos, self.endeol, 'str')
                    elif (tip and tip.content == ContentType.Inline and 
                          (not is_blank) and 
                          tip.inline_parser):
                        tip.inline_parser.feed(self.pos, self.endeol)

            self.pos = (self.endeol or self.pos) + 1
        # end while

        # close all remaining containers.
        self.last_matched_container = -1
        self.close_unmatched_containers()
        # return and accumulated matches
        while len(self.matches) > 0 and self.returned < len(self.matches):
            self.returned = self.returned + 1
            yield self.matches[self.returned - 1]

        yield Event(
            startpos=self.pos,
            endpos=self.pos,
            annot='',
        )

def parse_events(input_: str, options: Options):
    return EventParser(input_, options)

