import re

from .common import MatchedRange


# The TS version `find` is is a hack of JS regular expression,
# which is already implemented by Python re.Pattern.search.
def find(
    subject: str, 
    patt: re.Pattern, 
    startpos: int, 
    endpos: int | None = None
) -> MatchedRange | None:
    if endpos is not None:
        m = patt.search(subject, startpos, endpos + 1)
    else:
        m = patt.search(subject, startpos)

    if m:
        return MatchedRange(
            start=m.start(), # start of whole match.
            end=m.end()-1, # the last char of whole match.
            captures=list(m.groups()) # Match.groups() returns a tuple containing string or None.
        )