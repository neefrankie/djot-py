# In djot.js, this is called ContentType.
from enum import Enum, auto


class ContainerCap(Enum):
    NONE = auto()
    INLINE = auto()
    BLOCK = auto()
    TEXT = auto()
    CELLS = auto()
    ATTRIBUTES = auto()
    LIST_ITEM = auto()