from enum import Enum, StrEnum, auto
from dataclasses import dataclass
import re
from typing import List, NamedTuple

# --- 1. Enumerations ---

class OrdinalKind(StrEnum):
    DECIMAL = '1'    # 1, 2, 3
    LOWER_ROMAN = 'i'  # i, ii, iii
    UPPER_ROMAN = 'I'  # I, II, III
    LOWER_ALPHA = 'a'  # a, b, c
    UPPER_ALPHA = 'A'  # A, B, C

    def __str__(self) -> str:
            return self.value
    
    def __repr__(self) -> str:
        return f'OrdinalKind({self.name})'

class DelimiterKind(StrEnum):
    PERIOD = '.'     # '1.'
    PAREN = ')'      # '1)'
    TWO_PARENS = '()' # '(1)'

    def __str__(self) -> str:
                return self.value
        
    def __repr__(self) -> str:
        return f'DelimiterKind({self.name})'

class OrderedStyle(NamedTuple):
    ordinal: OrdinalKind
    delimiter: DelimiterKind

    def __str__(self) -> str:
        ordinal = self.ordinal.value
        match self.delimiter:
            case DelimiterKind.PERIOD:
                return f'{ordinal}.'
            case DelimiterKind.PAREN:
                return f'{ordinal})'
            case DelimiterKind.TWO_PARENS:
                return f'({ordinal})'

class BulletKind(StrEnum):
    PLUS = '+'
    DASH = '-'
    STAR = '*'

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f'BulletKind({self.name})'

class CheckboxKind(StrEnum):
    EMPTY = ' '
    LOWER_X = 'x'
    UPPER_X = 'X'

class TaskStyle(NamedTuple):
    bullet: BulletKind
    checkbox: CheckboxKind

    def __str__(self) -> str:
        return f'{self.bullet.value} [{self.checkbox.value}]'

class ListKind(Enum):
    BULLET = auto()
    TASK = auto()
    DEFINITION = auto()
    ORDERED = auto()

# --- 2. Target Specifications ---

@dataclass(frozen=True, slots=True)
class ListStyle:
    list_type: ListKind
    bullet: BulletKind | None = None
    task: TaskStyle | None = None
    ordered: OrderedStyle | None = None

    @property
    def is_task(self) -> bool:
        return self.list_type == ListKind.TASK

    @property
    def is_definition(self) -> bool:
        return self.list_type == ListKind.DEFINITION

    @property
    def is_bullet(self) -> bool:
        return self.list_type == ListKind.BULLET

    def __repr__(self) -> str:
        return f'ListStyle(list_type={self.list_type!r}, bullet={self.bullet!r}, task={self.task!r}, ordered={self.ordered!r})'

    def __str__(self) -> str:
        match self.list_type:
            case ListKind.BULLET:
                assert self.bullet is not None
                return self.bullet.value
            case ListKind.TASK:
                assert self.task is not None
                return str(self.task)
            case ListKind.DEFINITION:
                return ':'
            case ListKind.ORDERED:
                assert self.ordered is not None
                return str(self.ordered)

# --- 3. Intermediate Helper Types ---

class ParsedMarker(NamedTuple):
    """
    Tuple of decomposed marker.
    """
    delimiter: DelimiterKind # ., ), or ()
    ordinal: str # after stripping '.', ')' or '()'

# --- 4. Parser Implementation ---

_BULLET_MARKER = '+-*'
_TASK_CHECKER = {' [ ]', ' [x]', ' [X]'}
_PATT_DECIMAL = re.compile(r'[0-9]+')
_LOWER_ROMAN_SINGLE = {'i', 'v', 'x', 'l', 'c', 'd', 'm'}
_UPPER_ROMAN_SINGLE = {'I', 'V', 'X', 'L', 'C', 'D', 'M'}

# Verify the validity of roman numerals with two or more characters
_PATT_MULTI_LOWER_ROMAN = re.compile(r'[ivxlcdm]+')
_PATT_MULTI_UPPER_ROMAN = re.compile(r'[IVXLCDM]+')

def parse_task_marker(marker: str) -> TaskStyle | None:
    """
    - [ ]
    01234
    - [X]
    - [x]
    * [ ]
    * [X]
    * [x]
    + [ ]
    + [X]
    + [x]
    """
    if len(marker) == 5 and marker[0] in _BULLET_MARKER and marker[1:] in _TASK_CHECKER:
        return TaskStyle(
            bullet=BulletKind(marker[0]),
            checkbox=CheckboxKind(marker[3]),
        )
    return None


def parse_ordinal_style(ordinal: str) -> List[OrdinalKind]:
    """
    Args:
        ordinal: the string after stripping all delimiters.

    Returns:
        Candidates of ordered styles.
        When there are multiple candidates,
        the ambiguity should be resolved by following items.
        In case of resoling failure, the first one is selected.
    """
    # 1., 1), (1)
    if _PATT_DECIMAL.fullmatch(ordinal):
        return [OrdinalKind.DECIMAL]

    length = len(ordinal)
    if length == 0:
        return []

    if length == 1:
        ch = ordinal
        if ch in _LOWER_ROMAN_SINGLE:
            # i, v, x... could be either roman numeral or alpha
            return [
                OrdinalKind.LOWER_ROMAN,
                OrdinalKind.LOWER_ALPHA
            ]

        if ch in _UPPER_ROMAN_SINGLE:
            # I, V, X... could be either roman numeral or alpha
            return [
                OrdinalKind.UPPER_ROMAN,
                OrdinalKind.UPPER_ALPHA
            ]
        if 'a' <= ch <= 'z':
            return [OrdinalKind.LOWER_ALPHA]
        if 'A' <= ch <= 'Z':
            return [OrdinalKind.UPPER_ALPHA]
        return []

    # 3. Mutiple characters like ii, ix, xiv or AA, BC)
    # Roman numeral takes precedence over alpha
    if all('a' <= c <= 'z' for c in ordinal):
        if _PATT_MULTI_LOWER_ROMAN.fullmatch(ordinal):
            return [OrdinalKind.LOWER_ROMAN]
        # Multiple English characters are usually not allowed to be used in lists.
        return []

    if all('A' <= c <= 'Z' for c in ordinal):
        if _PATT_MULTI_UPPER_ROMAN.fullmatch(ordinal):
            return [OrdinalKind.UPPER_ROMAN]
        return []

    return []


def parse_ordered_delimiter(marker: str) -> ParsedMarker | None:
    if marker[0] == '(' and marker[-1] == ')':
        return ParsedMarker(
            delimiter=DelimiterKind.TWO_PARENS,
            ordinal=marker[1:-1]
        )
    
    if marker[-1] == ')':
        return ParsedMarker(
            delimiter=DelimiterKind.PAREN,
            ordinal=marker[:-1]
        )

    if marker[-1] == '.':
        return ParsedMarker(
            delimiter=DelimiterKind.PERIOD,
            ordinal=marker[:-1]
        )

    return None


def parse_ordered_marker(marker: str) -> List[OrderedStyle] | None:
    parsed = parse_ordered_delimiter(marker)
    if not parsed:
        return None

    delimiter, ordinal = parsed
    ordinals = parse_ordinal_style(ordinal)

    if not ordinals:
        return None

    return [
        OrderedStyle(
            ordinal=o,
            delimiter=delimiter
        )
        for o in ordinals
    ]

    
def parse_list_styles(marker: str) -> List[ListStyle]:
    if marker in _BULLET_MARKER:
        return [
            ListStyle(
                list_type=ListKind.BULLET,
                bullet=BulletKind(marker)
            )
        ]
    if marker == ':':
        return [
            ListStyle(
                list_type=ListKind.DEFINITION,
            )
        ]

    task_style = parse_task_marker(marker)
    if task_style:
        return [
            ListStyle(
                list_type=ListKind.TASK,
                task=task_style
            )
        ]

    ordered_styles = parse_ordered_marker(marker)

    if ordered_styles is not None:
        return [
            ListStyle(
                list_type=ListKind.ORDERED,
                ordered=s,
            )
            for s in ordered_styles
        ]

    return []

def intersect_list_styles(
    current: List[ListStyle],
    incoming: List[ListStyle],
) -> List[ListStyle]:
    incoming_set = set(incoming)
    return [item for item in current if item in incoming_set]