from abc import ABC, abstractmethod
from typing import Optional

from .state import InlineState

class Matcher(ABC):
    
    @abstractmethod
    def __call__(self, state: InlineState, pos: int, endpos: int) -> Optional[int]:
        pass