from dataclasses import dataclass
import string
from typing import Final


@dataclass(slots=True)
class Range:
    start: int
    end: int

    def shrink_end(self, end: int):
        self.start = end

    def __str__(self) -> str:
        return f'{self.start}:{self.end}'

@dataclass(slots=True)
class SourceLoc:
    line: int
    col: int
    offset: int

# In Python, str.isalnum() includes isalpha(), isdecimal(), isdigit().
# They are not exactly identifical to regex defined in djot.js:
# r'[a-zA-Z0-9_:-]'
# For isalpha, 'µ'.isalpha() since non-ASCII characters can be considered alphabetical too
# For isdecimal and isdigit, number in other language is also true
# This actually equals string.ascii_letters + string.digits + '_:-'
# Here's a strict version of ASCII char set permitted in key, bare value, id/class value.
# Corresponds to regex r'[a-zA-Z0-9_:-]'
_ASCII_NAME_CHARS: Final = frozenset(string.ascii_letters + string.digits + "_:-")

_ASCII_WHITESPACE = set(' \t\n\r\x0c')

def is_name_char(c: str) -> bool:
    return c in _ASCII_NAME_CHARS

def is_ascii_punctuation(c: str) -> bool:
    """
    Checks if the value is an ASCII punctuation character.
    
    Implement Rust char::is_ascii_punctuation()
    """
    return c in string.punctuation

def is_ascii_whitespace(c: str) -> bool:
    """
    Checks if the value is an ASCII whitespace character:
    U+0020 SPACE, 
    U+0009 HORIZONTAL TAB, \t, 
    U+000A LINE FEED, \n,
    U+000C FORM FEED, \f, or 
    U+000D CARRIAGE RETURN \r
    
    Implement Rust char::is_ascii_whitespace()
    Matches: space, tab, linefeed, carriage return and formfeed.
    """
    return c in _ASCII_WHITESPACE