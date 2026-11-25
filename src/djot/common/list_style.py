from enum import Enum, StrEnum, auto
from dataclasses import dataclass
from typing import List, NamedTuple

_LOWER_ROMAN = "ivxlcdm"
_UPPER_ROMAN = "IVXLCDM"

class BulletStyle(StrEnum):
    PLUS = '+'
    DASH = '-'
    STAR = '*'

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f'BulletKind({self.name})'

class CheckboxStyle(StrEnum):
    EMPTY = ' '
    LOWER_X = 'x'
    UPPER_X = 'X'

class TaskList(NamedTuple):
    style: BulletStyle
    checkbox: CheckboxStyle

    def __str__(self) -> str:
        return f'{self.style.value} [{self.checkbox.value}]'
    
class OrdinalKind(StrEnum):
    DECIMAL = '1'    # 1, 2, 3
    ROMAN_LOWER = 'i'  # i, ii, iii
    ROMAN_UPPER = 'I'  # I, II, III
    ALPHA_LOWER = 'a'  # a, b, c
    ALPHA_UPPER = 'A'  # A, B, C

    def __str__(self) -> str:
            return self.value
    
    def __repr__(self) -> str:
        return f'OrdinalKind({self.name})'

class OrderedListStyle(StrEnum):
    PERIOD = '.'     # '1.'
    PAREN = ')'      # '1)'
    TWO_PARENS = '()' # '(1)'

    def __str__(self) -> str:
                return self.value
        
    def __repr__(self) -> str:
        return f'DelimiterKind({self.name})'

class OrderedList(NamedTuple):
    ordinal: OrdinalKind
    style: OrderedListStyle

    def __str__(self) -> str:
        ordinal = self.ordinal.value
        match self.style:
            case OrderedListStyle.PERIOD:
                return f'{ordinal}.'
            case OrderedListStyle.PAREN:
                return f'{ordinal})'
            case OrderedListStyle.TWO_PARENS:
                return f'({ordinal})'


class ListKind(Enum):
    UNORDERED = auto()
    TASK = auto()
    DEFINITION = auto()
    ORDERED = auto()


@dataclass(frozen=True, slots=True)
class ListStyle:
    list_type: ListKind
    unordered: BulletStyle | None = None
    task: TaskList | None = None
    ordered: OrderedList | None = None

    @classmethod
    def new_defition(cls) -> 'ListStyle':
        return ListStyle(
            list_type=ListKind.DEFINITION,
        )

    @classmethod
    def new_bullet(cls, marker: str) -> 'ListStyle':
        return cls(
            list_type=ListKind.UNORDERED,
            unordered=BulletStyle(marker),
        )

    @classmethod
    def new_task(cls, marker: str, checker: str) -> 'ListStyle':
        return cls(
            list_type=ListKind.TASK,
            task=TaskList(
                style=BulletStyle(marker),
                checkbox=CheckboxStyle(checker),
            ),
        )

    @classmethod
    def new_ordered(cls, ordinal: OrdinalKind, delimiter: str) -> 'ListStyle':
        return cls(
            list_type=ListKind.ORDERED,
            ordered=OrderedList(ordinal, OrderedListStyle(delimiter)),
        )

    @property
    def is_task(self) -> bool:
        return self.list_type == ListKind.TASK

    @property
    def is_definition(self) -> bool:
        return self.list_type == ListKind.DEFINITION

    @property
    def is_bullet(self) -> bool:
        return self.list_type == ListKind.UNORDERED

    def __repr__(self) -> str:
        return f'ListStyle(list_type={self.list_type!r}, bullet={self.unordered!r}, task={self.task!r}, ordered={self.ordered!r})'

    def __str__(self) -> str:
        match self.list_type:
            case ListKind.UNORDERED:
                assert self.unordered is not None
                return self.unordered.value
            case ListKind.TASK:
                assert self.task is not None
                return str(self.task)
            case ListKind.DEFINITION:
                return ':'
            case ListKind.ORDERED:
                assert self.ordered is not None
                return str(self.ordered)



def classify_ordinal(ordinal: str) -> List[OrdinalKind]:
    if len(ordinal) == 1:
        if '0' <= ordinal <= '9':
            return [OrdinalKind.DECIMAL]
        
        if ordinal in _LOWER_ROMAN:
            return [
                OrdinalKind.ROMAN_LOWER,
                OrdinalKind.ALPHA_LOWER
            ]

        if ordinal in _UPPER_ROMAN:
            return [
                OrdinalKind.ROMAN_UPPER,
                OrdinalKind.ALPHA_UPPER
            ]

        if 'a' <= ordinal <= 'z':
            return [OrdinalKind.ALPHA_LOWER]
        if 'A' <= ordinal <= 'Z':
            return [OrdinalKind.ALPHA_UPPER]
        return []

    if all(c in _LOWER_ROMAN for c in ordinal):
        return [OrdinalKind.ROMAN_LOWER]

    if all (c in _UPPER_ROMAN for c in ordinal):
        return [OrdinalKind.ROMAN_UPPER]

    if all('a' <= c <= 'z' for c in ordinal):
        return [OrdinalKind.ALPHA_LOWER]

    if all('A' <= c <= 'Z' for c in ordinal):
        return [OrdinalKind.ALPHA_UPPER]

    return []


def intersect_list_styles(
    current: List[ListStyle],
    incoming: List[ListStyle],
) -> List[ListStyle]:
    incoming_set = set(incoming)
    return [item for item in current if item in incoming_set]