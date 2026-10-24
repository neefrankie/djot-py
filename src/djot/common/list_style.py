from enum import Enum, StrEnum, auto
from dataclasses import dataclass
from typing import List, NamedTuple

_LOWER_ROMAN = "ivxlcdm"
_UPPER_ROMAN = "IVXLCDM"

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


@dataclass(frozen=True, slots=True)
class ListStyle:
    list_type: ListKind
    bullet: BulletKind | None = None
    task: TaskStyle | None = None
    ordered: OrderedStyle | None = None

    @classmethod
    def new_defition(cls) -> 'ListStyle':
        return ListStyle(
            list_type=ListKind.DEFINITION,
        )

    @classmethod
    def new_bullet(cls, marker: str) -> 'ListStyle':
        return cls(
            list_type=ListKind.BULLET,
            bullet=BulletKind(marker),
        )

    @classmethod
    def new_task(cls, marker: str, checker: str) -> 'ListStyle':
        return cls(
            list_type=ListKind.TASK,
            task=TaskStyle(
                bullet=BulletKind(marker),
                checkbox=CheckboxKind(checker),
            ),
        )

    @classmethod
    def new_ordered(cls, ordinal: OrdinalKind, delimiter: str) -> 'ListStyle':
        return cls(
            list_type=ListKind.ORDERED,
            ordered=OrderedStyle(ordinal, DelimiterKind(delimiter)),
        )

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


def classify_ordinal(ordinal: str) -> List[OrdinalKind]:
    if len(ordinal) == 1:
        if '0' <= ordinal <= '9':
            return [OrdinalKind.DECIMAL]
        
        if ordinal in _LOWER_ROMAN:
            return [
                OrdinalKind.LOWER_ROMAN,
                OrdinalKind.LOWER_ALPHA
            ]

        if ordinal in _UPPER_ROMAN:
            return [
                OrdinalKind.UPPER_ROMAN,
                OrdinalKind.UPPER_ALPHA
            ]

        if 'a' <= ordinal <= 'z':
            return [OrdinalKind.LOWER_ALPHA]
        if 'A' <= ordinal <= 'Z':
            return [OrdinalKind.UPPER_ALPHA]
        return []

    if all(c in _LOWER_ROMAN for c in ordinal):
        return [OrdinalKind.LOWER_ROMAN]

    if all (c in _UPPER_ROMAN for c in ordinal):
        return [OrdinalKind.UPPER_ROMAN]

    if all('a' <= c <= 'z' for c in ordinal):
        return [OrdinalKind.LOWER_ALPHA]

    if all('A' <= c <= 'Z' for c in ordinal):
        return [OrdinalKind.UPPER_ALPHA]

    return []


def intersect_list_styles(
    current: List[ListStyle],
    incoming: List[ListStyle],
) -> List[ListStyle]:
    incoming_set = set(incoming)
    return [item for item in current if item in incoming_set]