from dataclasses import dataclass
from enum import StrEnum
import string
from typing import Final


@dataclass(slots=True)
class Range:
    start: int
    end: int

    def __str__(self) -> str:
        return f'{self.start}:{self.end}'

@dataclass(slots=True)
class SourceLoc:
    line: int
    col: int
    offset: int

@dataclass
class Pos:
    start: SourceLoc
    end: SourceLoc

class Alignment(StrEnum):
    DEFAULT = 'default'
    LEFT = 'left'
    RIGHT = 'right'
    CENTER = 'center'

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

def find_last_whitespace(s: str):
    last_space_idx = -1

    for i in range(len(s)-1, -1, -1):
        if s[i].isspace():
            last_space_idx = i
            break

    return last_space_idx


def unescape_djot(s: str) -> str:
    """
    Turn Djot-escaped string to plain text
    
    Used when rendering to convert Djot-escaped value in attributes list back to plain string.
    
    Examples:
        >>> unescape_djot('foo\\"bar')
        'foo"bar'
        >>> unescape_djot('foo\\\\bar')
        'foo\\bar'
        >>> unescape_djot('foo\\*bar')
        'foo*bar'
    """
    return ''.join(attribute_value_parts(s))


def attribute_value_parts(s: str):
    """
    Yields parts of unescaped string.
    """
    start = 0 # start of current slice
    i = 0 # start of find index.

    while i < len(s):
        j = s.find('\\', i) # find next backslash
        if j == -1:
            # No more backslashes
            yield s[start:]
            break

        # char after backslash
        if j + 1 < len(s):
            if s[j + 1] == '\\':
                # Unescape backslash
                yield s[i:j + 1]
                start = j + 2
                i = j + 2
            elif is_ascii_punctuation(s[j + 1]):
                # Unscape punctuation
                yield s[start:j]
                start = j + 1
                i = j + 1
            else:
                i = j + 1
        else:
            yield s[start:]
            break