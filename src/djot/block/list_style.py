from enum import Enum, auto
from dataclasses import dataclass
import re
from typing import List, NamedTuple

# --- 1. Enumerations ---

class OrderedStyle(Enum):
    DECIMAL = auto()      # 1, 2, 3
    LOWER_ROMAN = auto()  # i, ii, iii
    UPPER_ROMAN = auto()  # I, II, III
    LOWER_ALPHA = auto()  # a, b, c
    UPPER_ALPHA = auto()  # A, B, C

class Delimiter(Enum):
    PERIOD = auto()     # '1.'
    PAREN = auto()      # '1)'
    TWO_PARENS = auto() # '(1)'

# --- 2. Target Specifications ---

@dataclass(frozen=True, slots=True)
class BulletListSpec:
    """
    -, +, *
    """
    bullet_char: str



@dataclass(frozen=True, slots=True)
class DefinitionListSpec:
    """
    :
    """
    bullet_char: str = ':'

@dataclass(frozen=True, slots=True)
class TaskListSpec:
    """
    - [ ]
    - [X]
    - [x]
    * [ ]
    * [X]
    * [x]
    + [ ]
    + [X]
    + [x]
    """
    bullet_char: str # '-', '+', '*'
    checkbox_char: str # ' ', 'x', 'X'

    @property
    def checked(self) -> bool:
        return self.checkbox_char == 'x' or self.checkbox_char == 'X'

@dataclass(frozen=True, slots=True)
class OrderedListSpec:
    """
    1. 1), (1)
    a, a), (a)
    A, A), (A)
    i, i), (i)
    I, I), (I)
    ix., ix, ix)
    IX., IX), (IX)

    Roman numerals:

    I = 1
    V = 5
    X = 10
    L = 50
    C = 100
    D = 500
    M = 1000
    """
    style: OrderedStyle
    delimiter: Delimiter

@dataclass(frozen=True, slots=True)
class ListStyleSpec:
    bullet: BulletListSpec | None = None
    definition: DefinitionListSpec | None = None
    task: TaskListSpec | None = None
    ordered: List[OrderedListSpec] | None = None

# --- 3. Intermediate Helper Types ---

class ParsedMarker(NamedTuple):
    """
    Tuple of decomposed marker.
    """
    delimiter: Delimiter # ., ), or ()
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

def parse_task_marker(marker: str) -> TaskListSpec | None:
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
        return TaskListSpec(
            bullet_char=marker[0],
            checkbox_char=marker[3]
        )
    return None


def parse_ordinal_style(ordinal: str) -> List[OrderedStyle]:
    """
    Args:
        ordinal: the string after stripping all delimiters.
    """
    # 1., 1), (1)
    if _PATT_DECIMAL.fullmatch(ordinal):
        return [OrderedStyle.DECIMAL]

    length = len(ordinal)
    if length == 0:
        return []

    if length == 1:
        ch = ordinal
        if ch in _LOWER_ROMAN_SINGLE:
            # i, v, x... could be either roman numeral or alpha
            return [
                OrderedStyle.UPPER_ROMAN,
                OrderedStyle.UPPER_ALPHA
            ]

        if ch in _UPPER_ROMAN_SINGLE:
            # I, V, X... could be either roman numeral or alpha
            return [
                OrderedStyle.UPPER_ROMAN,
                OrderedStyle.UPPER_ALPHA
            ]
        if 'a' <= ch <= 'z':
            return [OrderedStyle.LOWER_ALPHA]
        if 'A' <= ch <= 'Z':
            return [OrderedStyle.UPPER_ALPHA]
        return []

    # 3. 多字符情况 (如 ii, ix, xiv 或 AA, BC)
    # 先匹配多位罗马数字
    if all('a' <= c <= 'z' for c in ordinal):
        if _PATT_MULTI_LOWER_ROMAN.fullmatch(ordinal):
            return [OrderedStyle.LOWER_ROMAN]
        # 如果不是合法罗马数字（如 "ab"），Djot 标准通常不支持多位英文字母，但若要支持可放开
        return []

    if all('A' <= c <= 'Z' for c in ordinal):
        if _PATT_MULTI_UPPER_ROMAN.fullmatch(ordinal):
            return [OrderedStyle.UPPER_ROMAN]
        return []

    return []


def parse_ordered_delimiter(marker: str) -> ParsedMarker | None:
    if marker[0] == '(' and marker[-1] == ')':
        return ParsedMarker(
            delimiter=Delimiter.TWO_PARENS,
            ordinal=marker[1:-1]
        )
    
    if marker[-1] == ')':
        return ParsedMarker(
            delimiter=Delimiter.PAREN,
            ordinal=marker[:-1]
        )

    if marker[-1] == '.':
        return ParsedMarker(
            delimiter=Delimiter.PERIOD,
            ordinal=marker[:-1]
        )

    return None


def parse_ordered_marker(marker: str) -> List[OrderedListSpec] | None:
    splitted = parse_ordered_delimiter(marker)
    if not splitted:
        return None

    delimiter, num = splitted
    styles = parse_ordinal_style(num)

    return [
        OrderedListSpec(
            style=s,
            delimiter=delimiter
        )
        for s in styles
    ]

    
def parse_marker(marker: str) -> ListStyleSpec:
    if marker in _BULLET_MARKER:
        return ListStyleSpec(
            bullet=BulletListSpec(bullet_char=marker)
        )
    if marker == ':':
        return ListStyleSpec(
            definition=DefinitionListSpec()
        )

    task_spec = parse_task_marker(marker)
    if task_spec:
        return ListStyleSpec(
            task=task_spec
        )

    ordered_specs = parse_ordered_marker(marker)

    return ListStyleSpec(
        ordered=ordered_specs
    )

