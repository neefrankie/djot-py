from .list_style import (
    OrderedList,
    OrdinalKind,
    OrderedListStyle,
)

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

def number_to_roman(x: int) -> str:
    if x < 0 or x >= 4000:
        return "?"

    rom = ""
    while x > 0:
        if x >= 1000:
            rom += 'M'
            x -= 1000
        elif x >= 900:
            rom += 'CM'
            x -= 900
        elif x >= 500:
            rom += 'D'
            x -= 500
        elif x >= 400:
            rom += 'CD'
            x -= 400
        elif x >= 100:
            rom += 'C'
            x -= 100
        elif x >= 90:
            rom += 'XC'
            x -= 90
        elif x >= 50:
            rom += 'L'
            x -= 50
        elif x >= 40:
            rom += 'XL'
            x -= 40
        elif x >= 10:
            rom += 'X'
            x -= 10
        elif x == 9:
            rom += 'IX'
            x -= 9
        elif x >= 5:
            rom += 'V'
            x -= 5
        elif x == 4:
            rom += 'IV'
            x -= 4
        elif x >= 1:
            rom += 'I'
            x -= 1
    return rom

def number_to_alpha(num: int, style: str) -> str:

    d0 = ord('a') if style.islower() else ord('A') # 97 for a, 65 for A

    num_str = []

    while num > 0:
        num, rem = divmod(num - 1, 26)
        num_str.append(chr(d0 + rem))

    return ''.join(reversed(num_str))

def number_to_str(num: int, kind: OrdinalKind) -> str:
    match kind:
        case OrdinalKind.DECIMAL:
            return str(num)
        case OrdinalKind.ALPHA_LOWER:
            return number_to_alpha(num, 'a')
        case OrdinalKind.ALPHA_UPPER:
            return number_to_alpha(num, 'A')
        case OrdinalKind.ROMAN_LOWER:
            return number_to_roman(num).lower()
        case OrdinalKind.ROMAN_UPPER:
            return number_to_roman(num).upper()

def format_number(num: int, ol: OrderedList) -> str:
    num_str = number_to_str(num, ol.ordinal)

    match ol.style:
        case OrderedListStyle.PAREN:
            return f'{num_str})'
        case OrderedListStyle.PERIOD:
            return f'{num_str}.'
        case OrderedListStyle.TWO_PARENS:
            return f'({num_str})'