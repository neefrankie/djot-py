from enum import Enum, StrEnum, auto
from dataclasses import dataclass
import re
from typing import List, NamedTuple

# --- 1. Enumerations ---

class OrdinalStyle(StrEnum):
    DECIMAL = '1'    # 1, 2, 3
    LOWER_ROMAN = 'i'  # i, ii, iii
    UPPER_ROMAN = 'I'  # I, II, III
    LOWER_ALPHA = 'a'  # a, b, c
    UPPER_ALPHA = 'A'  # A, B, C

class DelimiterStyle(StrEnum):
    PERIOD = '.'     # '1.'
    PAREN = ')'      # '1)'
    TWO_PARENS = '()' # '(1)'

class OrderedStyle(NamedTuple):
    ordinal: OrdinalStyle
    delimiter: DelimiterStyle

    def __str__(self) -> str:
        ordinal = self.ordinal.value
        match self.delimiter:
            case DelimiterStyle.PERIOD:
                return f'{ordinal}.'
            case DelimiterStyle.PAREN:
                return f'{ordinal})'
            case DelimiterStyle.TWO_PARENS:
                return f'({ordinal})'

class BulletStyle(StrEnum):
    PLUS = '+'
    DASH = '-'
    STAR = '*'

class CheckboxStyle(StrEnum):
    EMPTY = ' '
    LOWER_X = 'x'
    UPPER_X = 'X'

class TaskStyle(NamedTuple):
    bullet: BulletStyle
    checkbox: CheckboxStyle

    def __str__(self) -> str:
        return f'{self.bullet.value} [{self.checkbox.value}]'

class ListType(Enum):
    BULLET = auto()
    TASK = auto()
    DEFINITION = auto()
    ORDERED = auto()

# --- 2. Target Specifications ---

@dataclass(frozen=True, slots=True)
class ListStyle:
    list_type: ListType
    bullet: BulletStyle | None = None
    task: TaskStyle | None = None
    ordered: OrderedStyle | None = None

    @property
    def is_task(self) -> bool:
        return self.list_type == ListType.TASK

    @property
    def is_definition(self) -> bool:
        return self.list_type == ListType.DEFINITION

    @property
    def is_bullet(self) -> bool:
        return self.list_type == ListType.BULLET

    def __str__(self) -> str:
        match self.list_type:
            case ListType.BULLET:
                assert self.bullet is not None
                return self.bullet.value
            case ListType.TASK:
                assert self.task is not None
                return str(self.task)
            case ListType.DEFINITION:
                return ':'
            case ListType.ORDERED:
                assert self.ordered is not None
                return str(self.ordered)

# --- 3. Intermediate Helper Types ---

class ParsedMarker(NamedTuple):
    """
    Tuple of decomposed marker.
    """
    delimiter: DelimiterStyle # ., ), or ()
    ordinal: str # after stripping '.', ')' or '()'

# --- 4. Parser Implementation ---

_BULLET_MARKER = '+-*'
_TASK_CHECKER = {' [ ]', ' [x]', ' [X]'}
_PATT_DECIMAL = re.compile(r'[0-9]+')
_LOWER_ROMAN_SINGLE = {'i', 'v', 'x', 'l', 'c', 'd', 'm'}
_UPPER_ROMAN_SINGLE = {'I', 'V', 'X', 'L', 'C', 'D', 'M'}

# Verify the validity of roman numerals with two or more characters
_PATT_MULTI_LOWER_ROMAN = re.compile(r'^(?:iv|xl|cd|i{2,3}|v?i{0,3}|x{1,3}|l?x{0,3}|c{1,3}|d?c{0,3}|m{1,3})$')
_PATT_MULTI_UPPER_ROMAN = re.compile(r'^(?:IV|XL|CD|I{2,3}|V?I{0,3}|X{1,3}|L?X{0,3}|C{1,3}|D?C{0,3}|M{1,3})$')

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
            bullet=BulletStyle(marker[0]),
            checkbox=CheckboxStyle(marker[3]),
        )
    return None


def parse_ordinal_style(ordinal: str) -> List[OrdinalStyle]:
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
        return [OrdinalStyle.DECIMAL]

    length = len(ordinal)
    if length == 0:
        return []

    if length == 1:
        ch = ordinal
        if ch in _LOWER_ROMAN_SINGLE:
            # i, v, x... could be either roman numeral or alpha
            return [
                OrdinalStyle.UPPER_ROMAN,
                OrdinalStyle.UPPER_ALPHA
            ]

        if ch in _UPPER_ROMAN_SINGLE:
            # I, V, X... could be either roman numeral or alpha
            return [
                OrdinalStyle.UPPER_ROMAN,
                OrdinalStyle.UPPER_ALPHA
            ]
        if 'a' <= ch <= 'z':
            return [OrdinalStyle.LOWER_ALPHA]
        if 'A' <= ch <= 'Z':
            return [OrdinalStyle.UPPER_ALPHA]
        return []

    # 3. Mutiple characters like ii, ix, xiv or AA, BC)
    # Roman numeral takes precedence over alpha
    if all('a' <= c <= 'z' for c in ordinal):
        if _PATT_MULTI_LOWER_ROMAN.fullmatch(ordinal):
            return [OrdinalStyle.LOWER_ROMAN]
        # Multiple English characters are usually not allowed to be used in lists.
        return []

    if all('A' <= c <= 'Z' for c in ordinal):
        if _PATT_MULTI_UPPER_ROMAN.fullmatch(ordinal):
            return [OrdinalStyle.UPPER_ROMAN]
        return []

    return []


def parse_ordered_delimiter(marker: str) -> ParsedMarker | None:
    if marker[0] == '(' and marker[-1] == ')':
        return ParsedMarker(
            delimiter=DelimiterStyle.TWO_PARENS,
            ordinal=marker[1:-1]
        )
    
    if marker[-1] == ')':
        return ParsedMarker(
            delimiter=DelimiterStyle.PAREN,
            ordinal=marker[:-1]
        )

    if marker[-1] == '.':
        return ParsedMarker(
            delimiter=DelimiterStyle.PERIOD,
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
                list_type=ListType.BULLET,
                bullet=BulletStyle(marker)
            )
        ]
    if marker == ':':
        return [
            ListStyle(
                list_type=ListType.DEFINITION,
            )
        ]

    task_style = parse_task_marker(marker)
    if task_style:
        return [
            ListStyle(
                list_type=ListType.TASK,
                task=task_style
            )
        ]

    ordered_styles = parse_ordered_marker(marker)

    if ordered_styles is not None:
        return [
            ListStyle(
                list_type=ListType.ORDERED,
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