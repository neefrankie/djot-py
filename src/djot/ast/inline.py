from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..common import find_last_whitespace, SourceLoc, Pos

from .base import (
    HasText,
    HasChildren,
    InlineNode,
)


@dataclass(kw_only=True)
class Str(HasText, InlineNode):

    @property
    def tag(self) -> str:
        return 'str'

    def split_at_last_space(self) -> Optional['Str']:
        # hello world
        #      ^
        last_space_idx = find_last_whitespace(self.text)
        if last_space_idx < 0:
            return

        left_text = self.text[:last_space_idx+1]
        word_text = self.text[last_space_idx+1:]

        self.text = left_text
        word_pos: Optional[Pos] = None
        if self.pos:
            original_end = self.pos.end
            self.pos.end = SourceLoc(
                line=original_end.line,
                col=self.pos.start.col + last_space_idx,
                offset=self.pos.start.offset + last_space_idx,
            )
            word_pos = Pos(
                start=SourceLoc(
                    line=original_end.line,
                    col=original_end.col - last_space_idx + 1,
                    offset=original_end.offset - last_space_idx + 1,
                ),
                end=original_end,
            )

        return Str(
            text=word_text,
            pos=word_pos
        )


@dataclass(kw_only=True)
class SoftBreak(InlineNode):
    @property
    def tag(self) -> str:
        return 'soft_break'

@dataclass(kw_only=True)
class HardBreak(InlineNode):
    @property
    def tag(self) -> str:
        return 'hard_break'

@dataclass(kw_only=True)
class NonBreakingSpace(InlineNode):
    @property
    def tag(self) -> str:
        return 'non_breaking_space'

@dataclass(kw_only=True)
class Symb(InlineNode):
    alias: str

    @property
    def tag(self) -> str:
        return 'symb'
    
@dataclass(kw_only=True)
class Verbatim(HasText, InlineNode):
    """
    Verbatim content begins with a string of consecutive characters ` and 
    ends with an equal-lengthed string of consecutive backtick characters.
    `` Verbatim with a backtick ` character``
    """
    @property
    def tag(self) -> str:
        return 'verbatim'

@dataclass(kw_only=True)
class RawInline(HasText, InlineNode):
    """
    Raw inline content in any format may be included using a verbatim
    span followed by  {=FORMAT}:

    This is `<?php echo 'Hello world! ?>`{=html}.
    """

    format: str

    @property
    def tag(self) -> str:
        return 'raw_inline'

@dataclass(kw_only=True)
class InlineMath(HasText, InlineNode):
    """
    Einstein derived $`e=mc^2`
    """

    @property
    def tag(self) -> str:
        return 'inline_math'

@dataclass(kw_only=True)
class DisplayMath(HasText, InlineNode):
    """
    $$` x^n + y^n = z^n `
    """
    @property
    def tag(self) -> str:
        return 'display_math'

@dataclass(kw_only=True)
class Url(HasText, InlineNode):
    """
    <https://pandoc.org/lua-filters>
    """

    @property
    def tag(self) -> str:
        return 'url'

@dataclass(kw_only=True)
class Email(HasText, InlineNode):
    """
    <me@example.com>
    """

    @property
    def tag(self) -> str:
        return 'email'

@dataclass(kw_only=True)
class FootnoteReference(HasText, InlineNode):
    """
    Here is the reference.[^foo]
    """
    @property
    def tag(self) -> str:
        return 'footnote_reference'

class SmartPunctuationType(Enum):
    LEFT_SINGLE_QUOTE = 0
    RIGHT_SINGLE_QUOTE = 1
    LEFT_DOUBLE_QUOTE = 2
    RIGHT_DOUBLE_QUOTE = 3
    ELLIPSES = 4
    EM_DASH = 5
    EN_DASH = 6

@dataclass(kw_only=True)
class SmartPunctuation(HasText, InlineNode):
    type: SmartPunctuationType

    @property
    def tag(self) -> str:
        return 'smart_punctuation'

@dataclass(kw_only=True)
class Emph(HasChildren[InlineNode], InlineNode):

    @property
    def tag(self) -> str:
        return 'emph'

@dataclass(kw_only=True)
class Strong(HasChildren[InlineNode], InlineNode):

    @property
    def tag(self) -> str:
        return 'strong'

@dataclass(kw_only=True)
class Link(HasChildren[InlineNode], InlineNode):
    """
    Inline link: [My link text](http://example.com)
    Reference link: [My link text][foo bar]
    [foo bar]: http://example.com

    [My link text][]
    [My link text]: /url
    """
    
    destination: str | None
    reference: str | None

    @property
    def tag(self) -> str:
        return 'link'

@dataclass(kw_only=True)
class Image(HasChildren[InlineNode], InlineNode):
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

    @property
    def tag(self) -> str:
        return 'image'

@dataclass(kw_only=True)
class Span(HasChildren[InlineNode], InlineNode):
    """
    I can be helpful to [read the manual]{.big .red}.
    """

    @property
    def tag(self) -> str:
        return 'span'

@dataclass(kw_only=True)
class Mark(HasChildren[InlineNode], InlineNode):

    @property
    def tag(self) -> str:
        return 'mark'

@dataclass(kw_only=True)
class Superscript(HasChildren[InlineNode], InlineNode):
    """
    djot^TM^
    """

    @property
    def tag(self) -> str:
        return 'superscript'

@dataclass(kw_only=True)
class Subscript(HasChildren[InlineNode], InlineNode):
    """
    H~2~O
    """

    @property
    def tag(self) -> str:
        return 'subscript'

@dataclass(kw_only=True)
class Insert(HasChildren[InlineNode], InlineNode):
    """
    {+nice+}
    """

    @property
    def tag(self) -> str:
        return 'insert'

@dataclass(kw_only=True)
class Delete(HasChildren[InlineNode], InlineNode):
    """
    {-mean-}
    """

    @property
    def tag(self) -> str:
        return 'delete'

@dataclass(kw_only=True)
class DoubleQuoted(HasChildren[InlineNode], InlineNode):

    @property
    def tag(self) -> str:
        return 'double_quoted'

@dataclass(kw_only=True)
class SingleQuoted(HasChildren[InlineNode], InlineNode):

    @property
    def tag(self) -> str:
        return 'single_quoted'