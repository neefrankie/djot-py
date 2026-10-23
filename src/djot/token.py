from dataclasses import dataclass

from djot.common import Range

@dataclass(slots=True, frozen=True)
class DivFenceToken:
    colon_span: Range
    colons: str
    lang_span: Range | None = None

@dataclass(slots=True, frozen=True)
class CodeFenceToken:
    border_span: Range
    borders: str
    lang_span: Range | None = None
    is_raw: bool = False

@dataclass(slots=True, frozen=True)
class RefDefToken:
    label_span: Range
    label: str
    value_span: Range | None = None