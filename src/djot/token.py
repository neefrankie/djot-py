from dataclasses import dataclass

from djot.common import Range

@dataclass(slots=True, frozen=True)
class FencedDivToken:
    colon_span: Range
    colon_num: int
    lang_span: Range | None = None

