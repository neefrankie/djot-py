from dataclasses import dataclass
from typing import List

from djot.common import Range
from djot.common import ListStyle

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

@dataclass(slots=True, frozen=True)
class FootnoteDefToken:
    label_span: Range
    label: str
    end_pos: int

@dataclass(slots=True, frozen=True)
class ListMarkerToken:
    start: int
    end: int # the full range includes trailing whitespace: '- ', or '(1) ' or '- [ ] '
    marker: str
    styles: List[ListStyle]
    item_span: Range # '-', '(1)', '1)', '1.'
    checkbox_span: Range | None = None # [ ], [x], [X]

    def checker(self) -> str:
        if self.checkbox_span is None:
            return ''

        return self.marker[3]