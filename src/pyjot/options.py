from .ast import SourceLoc

class Warning:
    def __init__(self, message: str, pos: int | SourceLoc | None):
        self.message = message
        self.source_loc: SourceLoc | None = None
        self.offset: int | None = None
        if isinstance(pos, int):
            self.offset = pos
        elif isinstance(pos, SourceLoc):
            self.source_loc = pos
            self.offset = pos.offset

    def render(self) -> str:
        result = self.message
        if self.source_loc:
            result += f' at line {self.source_loc.line}, col {self.source_loc.col}'
        elif self.offset:
            result += f' at offset {self.offset}'

        return result
    
class Options:

    def warn(self, warning: Warning):
        pass