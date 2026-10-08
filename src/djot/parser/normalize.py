import re


_PATT_WHITESPACE = re.compile(r'[ \t\r\n]+')

def normalize_label(label: str) -> str:
    return _PATT_WHITESPACE.sub(' ', label.strip())


def trim_verbatim(text: str) -> str:
    if text.startswith(' `'):
        text = text[1:]

    if text.endswith('` '):
        text = text[:-1]
    
    return text

def replace_newline(s: str) -> str:
    return s.replace('\r', ' ').replace('\n', ' ')

def remove_newline(s: str) -> str:
    return s.replace('\r', '').replace('\n', '')

def normalize_raw_format(text: str) -> str:
    """Remove the leading and trailing curly braces and equals sign."""
    if text.startswith('{='):
        text = text[2:]
    elif text.startswith('='):
        text = text[1:]

    if text.endswith('}'):
        text = text[:-1]

    return text