import re


class UniqiueIdentifierGenerator:

    _INVALID_CHARS = re.compile(r'[\]\[~!@#$%^&*(){}`,.<>\\|=+/?\s]+')
    _MULTIPLE_SPACES = re.compile(r' +')
    
    def __init__(self):
        self.identifiers = set()

    def add(self, identifier: str):
        self.identifiers.add(identifier)

    def generate(self, s: str) -> str:
        # 转换为小写（通常 ID 是小写）
        s = s.lower()
        
        # 清理文本
        slug = self._clean_text(s)
        
        # 确保唯一性
        return self._ensure_unique(slug)
    
    def _clean_text(self, text: str) -> str:
        """清理文本，生成基础 slug"""
        # 特殊字符转空格
        cleaned = self._INVALID_CHARS.sub(' ', text)
        # 去除首尾空格
        cleaned = cleaned.strip()
        # 多个空格转连字符
        return self._MULTIPLE_SPACES.sub('-', cleaned)
    
    def _ensure_unique(self, base: str) -> str:
        """确保标识符唯一"""
        if not base:
            base = 's'
        
        counter = 0
        slug = base
        
        while slug in self.identifiers:
            counter += 1
            slug = f"{base}-{counter}"
        
        self.identifiers.add(slug)
        return slug