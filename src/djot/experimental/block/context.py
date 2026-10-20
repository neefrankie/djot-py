from dataclasses import dataclass

from ..cursor import Cursor, LineContext

@dataclass(slots=True)
class ParsingContext:
    """Data passed to a rule's methods
    
    Attributes:
        cursor: The input text and its current reading position
        is_covered: Is a container shadowned by innner container?
        last_span_end: last event's ending position
            
    NOTE:
        `is_covered` indicates top containers in a stack have higher precedence over a lower one. 
        For example, if a fenced div wraps code block, 
        the code block should claim the owership of any line starting with ::: rather than letting the containing fenced div to take it as ending markup.
    """
    cursor: Cursor
    line: LineContext
    is_covered: bool = False



"""
How many state are there?

For 'open' operation:
- Yield to next rule
- A rule in the loop does not apply, so break the loop, and may fallback to paragraph rule.
- Gobbled whole line, stop trying any rules immediately and go to next line.
- No rule should be tried and fallback to pragraph rule, such as  parsing attributes failed.

For 'continue' operation:
- A frame (rule) on stack applies, move to next position and try next frame
- A frame does not apply, so break the loop.
- Gobbled whole line, stop trying any frames immediately and go to next line.

For 'close' operation
- 
"""


