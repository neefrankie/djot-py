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
    total = 0
    prevdigit = 0
    i = len(s) - 1
    while i >= 0:
        c = s[i]
        if c not in roman_digits:
            raise Exception(f'Encountered bad character in roman numeral {s}')
        n = roman_digits[c]
        if n < prevdigit: # e.g. ix
            total -= n
        else:
            total += n
        prevdigit = n
        i -= 1

    return total


def get_list_start(marker: str, style: str) -> int | None:

    numtype = style.replace('(', '').replace(')', '').replace('.', '')
    s = marker.replace('(', '').replace(')', '').replace('.', '')

    match numtype:
        case '1':
            return int(s)
        case 'A':
            return ord(s[0]) - 65 + 1 # 65 = 'A'
        case 'a':
            return ord(s[0]) - 97 + 1
        case 'I':
            return roman_to_number(s)
        case 'i':
            return roman_to_number(s)
        case _:
            return None