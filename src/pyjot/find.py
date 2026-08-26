from dataclasses import dataclass
import re
from typing import List

@dataclass(frozen=True)
class FindResult:
    startpos: int
    endpos: int
    captures: List[str]

# The TS version `find` is is a hack of JS regular expression,
# which is already implemented by Python re.Pattern.search.
def find(
    subject: str, 
    patt: re.Pattern, 
    startpos: int, 
    endpos: int | None = None
) -> FindResult | None:
    if endpos is not None:
        m = patt.search(subject, startpos, endpos + 1)
    else:
        m = patt.search(subject, startpos)

    if m:
        return FindResult(
            startpos=m.start(), # start of whole match.
            endpos=m.end()-1, # the end of whole match.
            captures=list(m.groups()) # Match.groups() returns a tuple containing string or None.
        )