import re
from typing import List


_re_task_list_item = re.compile(r'^[+*-] \[[Xx ]\]')
# 1. ordered, decimal-enumerated, followed by period
# 1) ordered, decimal-enumerated, followed by parenthesis
# (1) ordered, decimal-enumerated, enclosed in parentheses
_re_decimal_item = re.compile(r'^[(]?[0-9]+[).]')
_re_decimal_multiple = re.compile(r'[0-9]+')
# a. ordered, lower-alpha-enumerated, followed by period
# a) ordered, lower-alpha-enumerated, followed by parenthesis
# (a) ordered, lower-alpha-enumerated, enclosed in parentheses
# i. 
# i)
# (i)
_re_lower_roman_alpha_item = re.compile(r'^[(]?[ivxlcdm][).]')
_re_lower_alpha_multiple = re.compile(r'[a-z]+')

# A. ordered, upper-alpha-enumerated, followed by period
# A) ordered, upper-alpha-enumerated, followed by parenthesis
# (A) ordered, upper-alpha-enumerated, enclosed in parentheses
# I. ordered, upper-roman-enumerated, followed by period
# I) ordered, upper-roman-enumerated, followed by parenthesis
# (I) ordered, upper-roman-enumerated, enclosed in parentheses
_re_upper_roman_alpha_item = re.compile(r'^[(]?[IVXLCDM][).]')
_re_upper_alpha = re.compile(r'[A-Z]+')

_re_lower_roman_item = re.compile(r'^[(]?[ivxlcdm]+[).]')
_re_upper_roman_item = re.compile(r'^[(]?[IVXLCDM]+[).]')

# a. 
# a) 
# (a) 
_re_lower_alpha_item = re.compile(r'^[(]?[a-z][).]')
_re_lower_alpha_single = re.compile(r'[a-z]')

# A. ordered, upper-alpha-enumerated, followed by period
# A) ordered, upper-alpha-enumerated, followed by parenthesis
# (A) ordered, upper-alpha-enumerated, enclosed in parentheses
_re_upper_alpha_item = re.compile(r'^[(]?[A-Z][).]')
_re_upper_alpha_single = re.compile(r'[A-Z]')

def get_list_styles(marker: str) -> List[str]:
    if marker == '+' or marker == '-' or marker == '*' or marker == ':':
        return [marker]
    elif _re_task_list_item.search(marker):
        return [marker[0] + "X"] # task list - include marker for consistency
    elif _re_decimal_item.search(marker):
        return [_re_decimal_multiple.sub('1', marker)]
    elif _re_lower_roman_alpha_item.search(marker):
        return [
            _re_lower_alpha_multiple.sub('i', marker),
            _re_lower_alpha_multiple.sub('a', marker)
        ]
    elif _re_upper_roman_alpha_item.search(marker):
        return [
            _re_upper_alpha.sub('I', marker),
            _re_upper_alpha.sub('A', marker)
        ]
    elif _re_lower_roman_item.search(marker):
        return [_re_lower_alpha_multiple.sub('i', marker)]
    elif _re_upper_roman_item.search(marker):
        return [_re_upper_alpha.sub('I', marker)]
    elif _re_lower_alpha_item.search(marker):
        return [_re_lower_alpha_single.sub('a', marker)]
    elif _re_upper_alpha_item.search(marker):
        return [_re_upper_alpha_single.sub('A', marker)]
    else:
        return []