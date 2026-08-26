from .token import (
    TokenType,
    Token,
    BacktickToken,
    HashToken,
)

DELIMITERS = [
    "*",
    "_",
    "~",
    "[",
    "]",
    "(",
    ")",
    "!",
    "#",
    "-",
    "+",
    "|",
    "{",
    "}",
    "\0"
]

class Lexer:
    def __init__(self, source: str):
        self._input = source
        self._position = 0
        self._next_poisition = 0
        self._ch = '\0'
        self._row = 1
        self._col = 0

        # Initially move current position to 0,
        # next position to 1,
        # and row to 1, column to 1.
        self.read_char()
    
    def read_char(self):
        if self._next_poisition >= len(self._input):
            self._ch = '\0'
        else:
            self._ch = self._input[self._next_poisition]

        # A new line.
        if self._ch == '\n':
            self._row += 1
            self._col = 0

        self._position = self._next_poisition
        self._col += 1

        self._next_poisition += 1
        
    
    def next_token(self) -> Token:
        match self._ch:
            case '*':
                tok = Token(
                    TokenType.STAR,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '_':
                tok = Token(
                    TokenType.UNDERSCORE,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '~':
                tok = Token(
                    TokenType.TILDE,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '`':
                start_col = self._col
                backtick_count = self.read_backtick()
                return BacktickToken(
                    type=TokenType.BACKTICK,
                    literal='`' * backtick_count,
                    row=self._row,
                    col=start_col,
                    count=backtick_count,
                )
            
            case '=':
                tok = Token(
                    TokenType.EQUAL,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '[':
                tok = Token(
                    TokenType.LBRACKET,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case ']':
                tok = Token(
                    TokenType.RBRACKET,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok

            case '(':
                tok = Token(
                    TokenType.LPAREN,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case ')':
                tok = Token(
                    TokenType.RPAREN,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '!':
                tok = Token(
                    TokenType.BANG,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '{':
                tok = Token(
                    TokenType.LBRACE,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '}':
                tok = Token(
                    TokenType.RBRACE,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '#':
                start_col = self._col
                hash_count = self.read_hash()
                return HashToken(
                    type=TokenType.HASH,
                    literal='#' * hash_count,
                    row=self._row,
                    col=start_col,
                    count=hash_count,
                )
            
            case '-':
                tok = Token(
                    TokenType.DASH,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '+':
                tok = Token(
                    TokenType.PLUS,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '|':
                tok = Token(
                    TokenType.PIPE,
                    literal=self._ch,
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case ' ':
                tok = Token(
                    TokenType.SPACE,
                    literal=' ',
                    row=self._row,
                    col=self._col
                )
                return tok
            
            case '\t':
                tok = Token(
                    TokenType.SPACE,
                    literal='\t',
                    row=self._row,
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '\n':                
                tok = Token(
                    TokenType.NEWLINE,
                    literal=self._ch,
                    row=self._row, 
                    col=self._col
                )
                self.read_char()
                return tok
            
            case '\r':
                row = self._row
                col = self._col

                lit = self.read_return()

                return Token(
                    TokenType.NEWLINE,
                    literal=lit,
                    row=row,
                    col=col
                )
                
            case '\0':
                tok = Token(
                    TokenType.EOF, 
                    literal='', 
                    row=self._row, 
                    col=self._col
                )
                self.read_char()
                return tok
            
            case _:
                row = self._row
                col = self._col
                text = self.read_text()
                return Token(
                    TokenType.TEXT,
                    literal=text,
                    row=row,
                    col=col
                )
            
    def read_backtick(self) -> int:
        backtick_count = 0
        while self._ch == '`':
            backtick_count += 1
            self.read_char()

        # Stops after last `
        return backtick_count
        
    def read_hash(self) -> int:
        hash_count = 0
        while self._ch == '#':
            hash_count += 1
            self.read_char()

        # Stops after last #
        return hash_count
    
    def read_return(self) -> str:
        if self.peek_char() == '\n':
            # Move to \n
            self.read_char()
            # Move after \n
            self.read_char()
            return '\n'

        else:
            self.read_char()
            return '\n'
    
    def read_text(self) -> str:
        position = self._position
        while self._ch not in DELIMITERS:
            if self._ch == '\n':
                if self.peek_char() == '\n':
                    break
            self.read_char()
        # Stops after regular text
        return self._input[position:self._position]

    def peek_char(self) -> str:
        if self._next_poisition >= len(self._input):
            return '\0'
        return self._input[self._next_poisition]
    
    
    
    

    
            
                