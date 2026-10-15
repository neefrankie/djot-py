from collections import defaultdict
from typing import Dict, Iterator, List, Optional, Tuple

from djot.common import unescape_djot
from .normalize import replace_newline


class AttrBuilder:
    __slots__ = ('_data', '_last_attr_key')

    def __init__(self, initial: Dict[str, str] | None = None):
        self._data: Dict[str, List[str]] = defaultdict(list)
        # record the key currently being processed.
        # key/value is split in event generation, so
        # you don't know which key a value belongs to.
        # They are eseentially async.
        self._last_attr_key: Optional[str] = None

        if initial:
            for k, v in initial.items():
                self._data[k] = [v]

    def reset(self):
        self._data.clear()
        self._last_attr_key = None

    def get(self, key: str) -> str | None:
        """读取属性值：class 特殊连接，其余 key 只取最新值"""
        values = self._data.get(key)
        if not values:
            return None
        
        if key == "class":
            return " ".join(values)
        
        # 普通属性直接取数组最后一个元素（Last-wins）
        return values[-1]

    def items(self) -> Iterator[Tuple[str, str]]:
        for k, v_list in self._data.items():
            if not v_list:
                continue
            if k == "class":
                yield k, ' '.join(v_list)
            else:
                yield k, v_list[-1]
            

    def set_id(self, val: str):
        """Override id"""
        self._data['id'] = [val]

    def has_id(self) -> bool:
        return 'id' in self._data

    def add_class(self, class_name: str) -> None:
        """append class"""
        self._data["class"].append(class_name)

    def set_key(self, key: str):
        self._last_attr_key = key
        self._data[key] = []

    def set_val(self, val: str):
        val = replace_newline(val)
        val = unescape_djot(val)
        if self._last_attr_key:
            self._data[self._last_attr_key] = [val]
        else:
            raise Exception('Encountered value without key')

    def merge(self, other: 'AttrBuilder' | Dict[str, str] | None):
        if not other:
            return

        if isinstance(other, AttrBuilder):
            for k, v_list in other._data.items():
                self._data[k].extend(v_list)
        else:
            for k, v in other.items():
                self._data[k].append(v)

    def transfer_to(self, target: 'AttrBuilder' | Dict[str, str]):
        if isinstance(target, AttrBuilder):
            for k, v_list in self._data.items():
                target._data[k].extend(v_list)
        else:
            for k, v in self.items():
                if k == 'class' and k in target:
                    target[k] += f'{target[k]} {v}'
                else:
                    target[k] = v

        self.reset()

    @property
    def is_empty(self) -> bool:
        return not bool(self._data)

    def build(self) -> Dict[str, str] | None:
        if not self._data:
            return None
        return dict(self.items())