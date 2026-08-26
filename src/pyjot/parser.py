from .lexer import Lexer

class Parser:
    def __init__(self, lex: Lexer):
        self.current_token = lex.next_token()
        self.peek_token = lex.next_token()
        self.lexer = lex

    def next_token(self):
        self.current_token = self.peek_token
        self.peek_token = self.lexer.next_token()


    