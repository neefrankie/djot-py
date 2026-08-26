from dataclasses import dataclass
from enum import StrEnum


class TokenType(StrEnum):
    ILLEGAL = "ILLEGAL"
    EOF = "EOF"

    # Inline tokens
    STAR = "*"
    UNDERSCORE = "_"
    TILDE = "~"

    BACKTICK = "`" # inline or block
    EQUAL = "="

    # Links
    LBRACKET = "["
    RBRACKET = "]"
    LPAREN = "("
    RPAREN = ")"
    BANG = "!"

    LBRACE = "{"
    RBRACE = "}"

    # Blocks
    # Meaningful only at the beginning of a line
    HASH = "#" # # title
    DASH = "-" # - list
    PLUS = "+" # + list
    PIPE = "|"

    SPACE = "SPACE"
    TAB = "\t"
    NEWLINE = "\n"
    TEXT = "TEXT"
    

@dataclass(frozen=True)
class Token:
    type: TokenType
    literal: str
    row: int
    col: int

@dataclass(frozen=True)
class BacktickToken(Token):
    count: int

@dataclass(frozen=True)
class HashToken(Token):
    count: int

