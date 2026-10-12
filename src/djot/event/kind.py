from enum import Enum, auto
from typing import Union


class Action(Enum):
    ENTER = auto()
    EXIT = auto()

class BlockContainer(Enum):
    ATTRIBUTES = auto() # {}
    ANNOTATION = auto() # +/-
    BLOCK_QUOTE = auto() # >
    CAPTION = auto() # ^
    CODE_BLOCK = auto() # ``` or ~~~
    DIV = auto() # :::
    FOOTNOTE = auto() # [^foo]
    HEADING = auto()
    LIST = auto()
    LIST_ITEM = auto()
    REFERENCE_DEFINITION = auto()
    PARA = auto()
    TABLE = auto()
    TABLE_ROW = auto()
    DOC = auto() # Placeholder for the root node

class BlockLeaf(Enum):
    BLANKLINE = auto()
    THEMATIC_BREAK = auto()
    TABLE_SEPARATOR = auto() # :---:

class VerbatimKind(Enum):
    """Inline verbatim variants"""
    DISPLAY_MATH = auto() # $$`...`
    INLINE_MATH = auto() # $`...`
    VERBATIM = auto() # `...`

class InlineContainer(Enum):
    ATTR = auto()
    DELETE = auto() # {- -}
    DESTINATION = auto() # ( )
    DOUBLE_QUOTED = auto() # "  "
    EMAIL = auto() # < >
    EMPH = auto() # _ _
    IMAGE_TEXT = auto() # [ ]
    LINK_TEXT = auto() # [ ]
    INSERT = auto() # {+ +}
    MARK = auto() # {= =}
    REFERENCE = auto() # [ ]
    SPAN = auto() # [ ]
    SINGLE_QUOTED = auto() # '  '
    SUBSCRIPT = auto() # +/-
    SUPERSCRIPT = auto() # +/-
    STRONG = auto() # * *
    TABLE_CELL = auto() # | |
    URL = auto() # < >
    

class InlineLeaf(Enum):
    CHECKBOX = auto() # X
    CODE_LANGUAGE = auto()
    EM_DASH = auto() # ---
    EN_DASH = auto() # --
    ELLIPSES = auto() # ...
    ESCAPE = auto() # \
    FOOTNOTE_REF = auto() # [^foo]
    HARD_BREAK = auto() # \+\n
    IMAGE_MARKER = auto() # !
    LEFT_SINGLE_QUOTE = auto() # ', {'
    LEFT_DOUBLE_QUOTE = auto() # ", {"
    NBSP = auto() # \ + space
    NOTE_LABEL = auto() # foo inside [^foo]
    OPEN_MARKER = auto() # { in braced delimiter, this is a redundant marker and should not be rendered.
    RAW_FORMAT = auto() # =FORMAT
    REFERENCE_KEY = auto() # reference link key [foo]: https://example.com
    REFERENCE_VALUE = auto() # reference link value
    RIGHT_SINGLE_QUOTE = auto() # ', '}
    RIGHT_DOUBLE_QUOTE = auto() # ", "}
    SOFT_BREAK = auto() # line break in inline content
    SYMBOL = auto() # smiley
    STR = auto()
    TABLE_SEPARATOR = auto() # :---:


# Atributes are all leaves.
class AttrKind(Enum):
    CLASS = auto()
    CLASS_MARKER = auto()
    EQUAL_MARKER = auto()
    ID = auto()
    ID_MARKER = auto()
    KEY = auto()
    QUOTE_MARKER = auto()
    SPACE = auto()
    VALUE = auto()

    def __str__(self) -> str:
        return self.name


EventKind = Union[
    BlockContainer,
    BlockLeaf,
    VerbatimKind,
    InlineContainer,
    InlineLeaf,
    AttrKind,
]