from djot.common.list_style import OrderedList, OrdinalKind

roman_digits = {
    'i': 1,
    'v': 5,
    'x': 10,
    'l': 50,
    'c': 100,
    'd': 500,
    'm': 1000,
    'I': 1,
    'V': 5,
    'X': 10,
    'L': 50,
    'C': 100,
    'D': 500,
    'M': 1000,
}

def roman_to_number(s: str) -> int:
    sum = 0
    prev = 0

    for c in reversed(s):
        if c not in roman_digits:
            raise Exception(f'Encountered bad character in roman numeral {s}')
        
        n = roman_digits[c]
        if n < prev: # e.g. ix
            sum -= n
        else:
            sum += n
        prev = n

    return sum

def alpha_to_number(s: str) -> int:
    d0 = ord('a') if s.islower() else ord('A') # 97 for a, 65 for A
    result = 0
    for i, ch in enumerate(reversed(s)):
        digit = ord(ch) - d0 + 1   # A=1, B=2, ..., Z=26
        result += digit * (26 ** i)
    return result


def parse_ordered_number(marker: str, style: OrderedList) -> int:

    s = marker.replace('(', '').replace(')', '').replace('.', '')

    match style.ordinal:
        case OrdinalKind.DECIMAL:
            return int(s)
        case OrdinalKind.ALPHA_UPPER | OrdinalKind.ALPHA_LOWER:
            return alpha_to_number(s)
        case OrdinalKind.ROMAN_UPPER | OrdinalKind.ROMAN_LOWER:
            return roman_to_number(s)