from typing import Callable, Dict, List
from dataclasses import dataclass
import re

from .event import Event
from .attributes import AttributeParser
from .options import Options, Warning
from .find import find

@dataclass
class Opener:
    match_index: int # Index in Event list.
    startpos: int
    endpos: int
    annot: str | None
    sub_match_index: int
    substartpos: int | None # For [ in [beautiful skyline](clouds.jpg), point to ]
    subendpos: int | None # point to (

@dataclass(frozen=True)
class AttrSlice:
    startpos: int
    endpos: int

type MatcherFn = Callable[['InlineParser', int, int], int | None]
type OpenTest = Callable[[InlineParser, int], bool]


C_TAB = 9 # \t
C_LF = 10 # \n
C_CR = 13 # \r
C_SPACE = 32
C_BANG = 33
C_DOUBLE_QUOTE = 34 # "
C_DOLLARS = 36 # $
C_SINGLE_QUOTE = 39 # '
C_LEFT_PAREN = 40 # (
C_RIGHT_PAREN = 41 # )
C_ASTERISK = 42 # *
C_PLUS = 43 # +
C_HYPHEN = 45 # -
C_PERIOD = 46 # .
C_COLON = 58 # :
C_LESSTHAN = 60 # <
C_EQUALS = 61 # =
C_LEFT_BRACKET = 91 # []
C_BACKSLASH = 92 # \
C_RIGHT_BRACKET = 93 # ]
C_HAT = 94 # ^
C_UNDERSCORE = 95 # _
C_BACKTICK = 96 # `
C_LEFT_BRACE = 123 # {
C_RIGHT_BRACE = 125 # }
C_TILDE = 126 # ~

re_special = re.compile(
    r'''[\r\n"'()*+.:<=\[\\\]^_`${}~-]''' # NOTE: [, \, ]
)

def find_special(s: str, startpos: int, endpos: int) -> int | None:
    m = re_special.search(s, startpos, endpos)

    if m:
        return m.start()
    
    return None

patt_non_space = re.compile(r'[^ \t\r\n]')
patt_line_end = re.compile(r'[ \t]*\r?\n')
patt_punctuation = re.compile(
    r'''['!"#%&\\'()*+,\-./:;<=>?@\[\]^`{|}~']'''
)
# <https://pandoc.org/lua-filters>
# <me@example.com>
patt_autolink = re.compile(r'<([^<>\s]+)>')
patt_delim = re.compile(r'''[_*~^+='"-]''')
patt_symbol = re.compile(r':[\w_+-]+:')
patt_two_periods = re.compile(r'\.\.')
patt_backticks0 = re.compile(r'`*')
patt_backticks1 = re.compile(r'`+')
patt_double_dollars = re.compile(r'\$\$')
patt_single_dollar = re.compile(r'\$')
patt_backslash = re.compile(r'\\')
# {=FORMAT}
patt_raw_attribute = re.compile(r'\{=[^\s{}`]+\}')
# [^foo]
patt_note_reference = re.compile(r'\^([^\]]+)\]')

def has_brace(self: 'InlineParser', pos: int) -> bool:
    return (pos > 0 and ord(self.subject[pos-1]) == C_LEFT_BRACE) or ord(self.subject[pos+1]) == C_RIGHT_BRACE

def always_true(self: 'InlineParser', pos: int) -> bool:
    return True

def can_open_single_quote(self: 'InlineParser', pos: int) -> bool:
    if pos == 0:
        return True
    
    cp = ord(self.subject[pos-1])
    # <space/tab/cr/lf>'
    # "'
    # ''
    # -'
    # ('
    # ['
    return (cp == C_SPACE or
            cp == C_TAB or
            cp == C_CR or
            cp == C_LF or
            cp == C_DOUBLE_QUOTE or
            cp == C_SINGLE_QUOTE or
            cp == C_HYPHEN or
            cp == C_LEFT_PAREN or
            cp == C_LEFT_BRACKET)


_re_email = re.compile(r'[^:]@')
_re_url = re.compile(r'[a-zA-Z]:/')
_re_right = re.compile(r'^right')
_re_left = re.compile(r'^left')

def make_between_matched(
    c: str,
    annotation: str,
    defaultmatch: str,
    opentest: OpenTest,
) -> MatcherFn:
    """
    H~2~O
    20^th^
    _italic_
    *bold*
    {+insert+}
    {=highlighted=}
    {-delete-}
    """
    
    def returned_func(self: 'InlineParser', pos: int, endpos: int) -> int | None:
        # Example: H~2~O
        # The opening marker should not have space after it,
        # while the closing marker should not have space before it.
        can_open = find(self.subject, patt_non_space, pos+1) is not None and opentest(self, pos)
        can_close = find(self.subject, patt_non_space, pos-1) is not None
        
        lastmatch = self.matches[len(self.matches)-1]
        # In cases of ambiguity, `{` and `}` may be used to mark delimiters as
        # openers or closers. Thus `{_` behaves like `_` but can _only_ open
        # emphasis, while `_}` behaves like `_` but can _only_ close emphasis:
        # {_Emphasized_}
        # Explicitly marked closers can only match explicitly marked
        # openers, and non-marked closers can only match non-marked
        has_open_marker = lastmatch and lastmatch.annot == "open_marker" # open_marker is created when { is first seen.
        has_close_marker = pos+1 <= endpos and ord(self.subject[pos+1]) == C_RIGHT_BRACE
        
        # current pos could be either start or end marker.
        endcloser = pos
        startopener = pos

        # Allow explicit open/close markers to override
        # When you have `{` before `c`, that is, `{_`,
        # you are ensured with opening markder.
        if has_open_marker:
            can_open = True
            can_close = False
            startopener = pos-1

        if (not has_open_marker) and has_close_marker:
            can_close = True
            can_open = False
            endcloser = pos+1

        # Python closure rule: inner function could read external variable
        # but cannot modify it. If you reassign it, the interpreter
        # take it as defining a new local variable.
        _default_match = defaultmatch
        # betweenMatched("'", "single_quoted", "right_single_quote", ...)
        if has_open_marker and _re_right.match(defaultmatch):
            _default_match = _re_right.sub('left', defaultmatch)
        elif has_close_marker and _re_left.match(defaultmatch):
            # betweenMatched('"', "double_quoted", "left_double_quote", ...)
            _default_match = _re_left.sub('right', defaultmatch)

        d = c
        # If pos is closing marker with },
        # create opening marker as search key.
        if has_close_marker:
            d = '{' + d

        # Find all openers for the search key
        openers = self.openers[d]

        # If this is closing marker and there are corresponding opener markers.
        if can_close and openers and len(openers) > 0:
            # Check operners for a match
            # For _italic_, opener is leading _
            opener = openers[len(openers)-1] # closest opener.
            # If there are content between opening and closing marker.
            if opener.endpos != pos-1:
                # True for [My link text](http://example.com)
                # But why it handles link here since paren does not call this function.
                # _here [My link_ text]
                if self.destination:
                    link_openers = self.openers['[']
                    if link_openers and len(link_openers) > 0:
                        link_opener = link_openers[len(link_openers)-1]
                        # closer is inside link text.
                        if link_opener.annot == 'explicit_link' and opener.startpos < link_opener.startpos:
                            self.add_match(pos, endcloser, _default_match)
                            return endcloser+1
                # Clear all opening marker within range, including current one
                # Forbid overlapping
                self.clear_openers(opener.startpos, pos)
                # Replace old opening marker
                self.add_match(opener.startpos, opener.endpos, '+'+annotation, opener.match_index)
                self.add_match(pos, endcloser, '-'+annotation)
                return endcloser+1
            # Not closing marker, or not openers.
            
        if can_open:
            e = c
            if has_open_marker:
                e = '{'+e
            self.add_opener(e, startopener, pos, _default_match)
            return pos+1
        else:
            # Fallback.
            self.add_match(pos, endcloser, _default_match)
            return endcloser+1

    return returned_func

def handle_backtick(
    self: 'InlineParser', 
    pos: int, 
    endpos: int
) -> int | None:
    # Find zero or more backtick
    m = find(self.subject, patt_backticks0, pos, endpos)
    if m is None:
        return None
    
    # Now we have opening backtick.
    endchar = m.endpos # position of last found backtick
    # $$` x^n + y^n = z^n `
    # If previous two characters are $$, and not preceded by a backslash,
    # it's a display math.
    if find(self.subject, patt_double_dollars, pos-2) and (not find(self.subject, patt_backslash, pos-3)):
        self.matches.pop() # remove first $
        self.matches.pop() # remove second $
        # $$`
        self.add_match(pos-2, endchar, '+display_math')
        self.verbatim_type = "display_math"
    elif find(self.subject, patt_single_dollar, pos-1):
        self.matches.pop() # remove $
        self.add_match(pos-1, endchar, '+inline_math')
        self.verbatim_type = "inline_math"
    else:
        self.add_match(pos, endchar, '+verbatim')
        self.verbatim_type = "verbatim"
    self.verbatim = endchar - pos + 1 # length of markers like $$`, $` or any amount of `.
    return endchar+1 # after `

def handle_backslash(
    self: 'InlineParser', 
    pos: int, 
    endpos: int
) -> int | None:
    # Inspect if characters following \ are [ \t]*\r?\n
    m_line_end = find(self.subject, patt_line_end, pos+1, endpos)
    # Backslash at end of line = hard line break.
    if m_line_end is not None:
        # see if there were preceding spaces and remove them.
        if len(self.matches) > 0:
            lastmatch = self.matches[len(self.matches)-1]
            if lastmatch.annot == 'str':
                ep = lastmatch.endpos
                sp = lastmatch.startpos
                while ep >= sp and (ord(self.subject[ep]) == C_SPACE or ord(self.subject[ep]) == C_TAB):
                    ep = ep - 1
                if ep < sp:
                    self.matches.pop() # space only
                else:
                    lastmatch.endpos = ep # change endpos to first non-space char.
        # \ is escape
        self.add_match(pos, pos, "escape")
        # The following is hard break.
        self.add_match(pos+1, m_line_end.endpos, "hard_break")
        return m_line_end.endpos + 1 # newpos starts after newline.
    else:
        # check if it is any punctuations
        m_punct = find(self.subject, patt_punctuation, pos+1, endpos)
        # You might write somthihg like
        # \!, \", \#, \%, \&
        if m_punct is not None:
            # \ is escape
            self.add_match(pos, pos, "escape")
            self.add_match(m_punct.startpos, m_punct.endpos, 'str')
            return m_punct.endpos + 1
        elif pos + 1 <= endpos and ord(self.subject[pos+1]) == C_SPACE:
            # \<space>
            self.add_match(pos, pos, "escape")
            self.add_match(pos+1, pos+1, "non_breaking_space")
            return pos+2
        else:
            # Plain \
            self.add_match(pos, pos, "str")
            return pos+1
        
def handle_lessthan(
    self: 'InlineParser', 
    pos: int, 
    endpos: int
) -> int | None:
    # <([^<>\s]+)>
    # <https://pandoc.org/lua-filters>
    # <me@example.com>
    m = find(self.subject, patt_autolink, pos, endpos)
    if m is None:
        return None
    
    endurl = m.endpos
    starturl = m.startpos
    url = m.captures[0]
    if _re_email.search(url):
        self.add_match(starturl, starturl, "+email") # <
        self.add_match(starturl+1, endurl-1, "str") # email
        self.add_match(endurl, endurl, "-email") # >
        return endurl+1 # after  >
    elif _re_url.search(url):
        self.add_match(starturl, starturl, "+url") # <
        self.add_match(starturl+1, endurl-1, "str") # url
        self.add_match(endurl, endurl, "-url") # >
        return endurl+1 # after >
    
    return None

def handle_left_brace(self: 'InlineParser', pos: int, endpos: int) -> int | None:
    # { followed by any _*~^+='"-
    # {_italic_}
    # {*bold*}
    # H~2~O
    # 20^th^
    # {+insert+}
    # {=heighlight=}
    # {''}
    # {""}
    # {- -}
    # Implicit precedence: delimiter > attribute > plain text
    if find(self.subject, patt_delim, pos+1, endpos):
        self.add_match(pos, pos, "open_marker") # {
        return pos+1
    elif self.allow_attributes:
        self.attribute_parser = AttributeParser(self.subject)
        self.attribute_start = pos # attribute starts from {
        self.attribute_slices = []
        return pos # parse from {
    else:
        self.add_match(pos, pos, 'str') # literal {
        return pos+1

def handle_colon(self: 'InlineParser', pos: int, endpos: int) -> int | None:
    # :[\w_+-]+:
    # Surrounding a word with `:` signs creates a "symbol," which by
    # default is just rendered literally but may be treated specially
    # by a filter.
    # My reaction is :+1: :smiley:.
    # Implicit precedence: symbol > plain text
    m = find(self.subject, patt_symbol, pos, endpos)
    if m:
        self.add_match(m.startpos, m.endpos, 'symb') # :smiley:
        return m.endpos+1 # after closing :
    else:
        self.add_match(pos, pos, 'str') # : is plain text.
        return pos+1
    
def handle_period(self: 'InlineParser', pos: int, endpos: int) -> int | None:
    # ...
    if find(self.subject, patt_two_periods, pos+1, endpos):
        self.add_match(pos, pos+2, 'ellipses') # ...
        return pos+3
    else:
        return None
    
def handle_left_bracket(self: 'InlineParser', pos: int, endpos: int) -> int | None:
    # \^([^\]]+)\]
    # [^proof]
    m = find(self.subject, patt_note_reference, pos+1, endpos) # test from ^
    if m:
        self.add_match(pos, m.endpos, 'footnote_reference') # [^proof]
        return m.endpos+1
    else:
        self.add_opener('[', pos, pos, 'str')
        return pos+1
    
def handle_right_bracket(self: 'InlineParser', pos: int, endpos: int) -> int | None:
    openers = self.openers['[']
    if openers and len(openers) > 1:
        opener = openers[len(openers)-1]
        # Reference links use a reference label in square brackets, 
        # instead of a destination in parentheses.
        # [My link text][foo bar]
        # ![picture of a cat](cat.jpg)
        # [My link text](http://example.com)
        # [a span]{.some-class #some-id some-key="some val"
        if opener.annot == 'reference_link':
            # found a reference link
            # convert all matches inside reference to str
            # Anything between opener and pos should be treated as plain text.
            self.str_matches((opener.subendpos or opener.endpos)+1, pos-1)
            # For ![ but not \![
            is_image = ord(self.subject[opener.startpos-1]) == C_BANG and ord(self.subject[opener.startpos-2]) != C_BACKSLASH

            if is_image:
                # Replace the ! Event.
                self.add_match(opener.startpos-1, opener.startpos-1, 'image_marker', opener.match_index-1)
                # Replace the [ Event.
                self.add_match(opener.startpos, opener.endpos, '+imagetext', opener.match_index)
                # TODO: what is this?
                self.add_match(
                    opener.substartpos or opener.startpos,
                    opener.substartpos or opener.startpos,
                    '-imagetext',
                    opener.sub_match_index
                )
            else:
                self.add_match(
                    opener.startpos,
                    opener.endpos,
                    '+linktext',
                    opener.match_index,
                )
                self.add_match(
                    opener.substartpos or opener.startpos,
                    opener.substartpos or opener.startpos,
                    '-linktext',
                    opener.sub_match_index,
                )
            
            # TODO: what is this?
            self.add_match(
                opener.subendpos or opener.endpos,
                opener.subendpos or opener.endpos,
                '+reference',
                opener.sub_match_index+1
            )
            self.add_match( # current ]
                pos,
                pos,
                '-reference'
            )
            self.clear_openers(opener.startpos, pos)
            return pos+1
        elif pos+1 <= endpos and ord(self.subject[pos+1]) == C_LEFT_BRACKET:
            # Next char is left [
            # [My link text][foo bar]
            opener.annot = 'reference_link'
            self.add_match(pos, pos, 'str') # ]. Why str?
            opener.sub_match_index = len(self.matches) - 1 # last match
            self.add_match(pos+1, pos+1, 'str') # [
            opener.substartpos = pos # intermediate ]
            opener.subendpos = pos+1 # [
            # remove any openers between [ and ]
            self.clear_openers(opener.startpos+1, pos-1)
            return pos+2 # after ][
        elif pos+1 <= endpos and ord(self.subject[pos+1]) == C_LEFT_PAREN:
            # Next char is (
            # [My link text](http://example.com)
            self.openers['('] = [] # clear ( openers
            opener.annot = 'explicit_link'
            self.add_match(pos, pos, 'str') # ]
            opener.sub_match_index = len(self.matches) - 1 # match created by last line.
            self.add_match(pos+1, pos+1, 'str') # (
            opener.substartpos = pos # intermediate ]
            opener.subendpos = pos + 1 # intemediate (
            self.destination = True
            # remove any openers betweeen [ and ]
            self.clear_openers(opener.startpos + 1, pos - 1)
            return pos + 2 # after ](
        elif pos+1 <= endpos and ord(self.subject) == C_LEFT_BRACE:
            # assume this is attributes, bracketed span.
            # [a span]{.some-class #some-id some-key="some val"}
            self.add_match(
                opener.startpos,
                opener.endpos,
                '+span',
                opener.match_index,
            )
            self.add_match(pos, pos, '-span')
            # remove any openers between [ and ]
            self.clear_openers(opener.startpos, pos)
            return pos+1 # {
    
    return None

def handle_left_paren(self: 'InlineParser', pos: int, endpos: int) -> int | None:
    # (
    if not self.destination:
        return None
    self.add_opener('(', pos, pos, 'str')
    return pos+1

def handle_right_paren(self: 'InlineParser', pos: int, endpos: int) -> int | None:
    # )
    # ![beautiful skyline](clouds.jpg)
    # [read more](https://example.com)
    if not self.destination:
        return None
    
    parens = self.openers['(']
    if parens and len(parens) > 0:
        parens.pop() # clear opener
        self.add_match(pos, pos, 'str')
        return pos+1
    else:
        openers = self.openers['[']
        opener = openers[len(openers) - 1]
        if opener and len(openers) > 0 and opener.annot == 'explicit_link':
            # we have inline link
            # convert all matches inside destination to str
            # [My link text](http://example.com)
            # opener.subendpos point to (
            self.str_matches((opener.subendpos or opener.endpos)+1, pos-1)
            is_image = (ord(self.subject[opener.startpos-1]) == C_BANG and
                        ord(self.subject[opener.startpos-2]) != C_BACKSLASH)

            if is_image:
                # Replace !
                self.add_match(
                    opener.startpos-1, 
                    opener.startpos-1,
                    'image_marker',
                    opener.match_index-1
                )
                # [
                self.add_match(
                    opener.startpos,
                    opener.endpos,
                    '+imagetext',
                    opener.match_index
                )
                # ]
                self.add_match(
                    opener.substartpos or opener.startpos,
                    opener.substartpos or opener.startpos,
                    '-imagetext',
                    opener.sub_match_index,
                )
            else:
                # [
                self.add_match(
                    opener.startpos,
                    opener.endpos,
                    '+linktext',
                    opener.match_index,
                )
                # ]
                self.add_match(
                    opener.substartpos or opener.startpos,
                    opener.substartpos or opener.startpos,
                    '-linktext',
                    opener.sub_match_index
                )
            # (
            self.add_match(
                opener.subendpos or opener.endpos,
                opener.subendpos or opener.endpos,
                '+destination',
                opener.sub_match_index+1
            )
            self.add_match(pos, pos, '-destination') # current )
            self.destination = False
            self.clear_openers(opener.startpos, pos) # From [ to )
            return pos+1 # after )
        
    return None

def handle_hyphen(self: 'InlineParser', pos: int, endpos: int) -> int | None:
    # {-delete-}
    if ord(self.subject[pos-1]) == C_LEFT_BRACE or ord(self.subject[pos+1]) == C_RIGHT_BRACE: # {- or -}
        newpos = make_between_matched(
            c='-',
            annotation='delete',
            defaultmatch='str',
            opentest=has_brace,
        )(self, pos, endpos)
        if newpos:
            return newpos
        
    # Didn't match a del, try for smart hyphen.
    ep = pos
    hyphens = 0
    while ep <= endpos and ord(self.subject[ep]) == C_HYPHEN:
        ep += 1 # if pos == endpos, only one loop
        hyphens += 1

    if ord(self.subject[ep]) == C_RIGHT_BRACE: # -}
        hyphens -= 1 # last hyphen is close del

    if hyphens == 0: # this means we have '-}'
        self.add_match(pos, pos+1, 'str')
        return pos+2
    
    # Try to contruct a homogeneous sequence of dashes
    # -- for en-dash
    # --- for em-dash
    all_em = hyphens % 3 == 0
    all_en = hyphens % 2 == 0
    while hyphens > 0:
        if all_em:
            self.add_match(pos, pos+2, 'em_dash')
            pos = pos + 3
            hyphens = hyphens - 3
        elif all_en:
            self.add_match(pos, pos+1, 'en_dash')
            pos = pos + 2
            hyphens = hyphens - 2
        elif hyphens >= 3 and (hyphens % 2 != 0 or hyphens > 4): # odd number of dashes
            self.add_match(pos, pos+2, 'em_dash')
            pos = pos + 3
            hyphens = hyphens - 3
        elif hyphens >= 2:
            self.add_match(pos, pos+1, 'en_dash')
            pos = pos + 2
            hyphens = hyphens - 2
        else:
            self.add_match(pos, pos, 'str')
            pos = pos + 1
            hyphens = hyphens - 1
    
    return pos



class InlineParser:
    def __init__(self, subject: str, options: Options):
        self.options = options
        self.warn = options.warn
        self.subject = subject
        self.matches: List[Event] = [] # array of matches

        # map from opener type to Opener[] in reverse order
        # Each entry is a stack.
        self.openers: Dict[str, List[Opener]] = {} 

        # parsing a verbatim span to be ended by N backticks
        self.verbatim = 0 # length of verbatim markers.
        self.verbatim_type = "" # math or regular

        self.destination = False # parsing link destination?

        self.firstpos = -1 # position of first slice
        self.lastpos = 0 # position of last slice

        self.allow_attributes = True # allow parsing of attributes.
        self.attribute_parser: AttributeParser | None = None
        self.attribute_start: int | None = None # start pos of potential attribute
        self.attribute_slices: List[AttrSlice] | None = None # slices we've tried to parse as attributes
        self.matchers = MATCHERS # funcitons to handle different code points

    def add_match(
        self, 
        startpos: int, 
        endpos: int, 
        annot: str, 
        match_index: int | None = None # replace at specified position
    ):
        m = Event(
            startpos=startpos,
            endpos=endpos,
            annot=annot,
        )

        if match_index is not None:
            self.matches[match_index] = m
        else:
            self.matches.append(m)

    def in_verbatim(self) -> bool:
        return self.verbatim > 0
    
    def single_char(self, pos: int) -> int:
        self.add_match(pos, pos, 'str')
        return pos + 1
    
    def reparse_attributes(self):
        slices = self.attribute_slices
        if slices is None:
            return
        
        self.allow_attributes = False
        self.attribute_parser = None
        self.attribute_start = None
        if slices is not None:
            for s in slices:
                self.feed(s.startpos, s.endpos)

        self.allow_attributes = True
        self.attribute_slices = None

    def get_matches(self) -> List[Event]:
        if self.attribute_parser:
            self.reparse_attributes()

        i = len(self.matches) - 1

        # remove trailing softbreak and any spaces
        if self.matches[i] and self.matches[i].annot == 'softbreak':
            self.matches.pop()
            m = self.matches[len(self.matches) - 1]
            
            if m and m.annot == 'str' and ord(self.subject[m.endpos]) == 32:
                
                while m.endpos >= m.startpos and ord(self.subject[m.endpos]) == 32:
                    m.endpos -= 1

                if m.endpos < m.startpos:
                    self.matches.pop()

        if len(self.matches) > 0 and self.verbatim > 0:
            # unclosed verbatim
            last = self.matches[len(self.matches) - 1]
            self.warn(Warning(
                message='Unclosed verbatim',
                pos=last.endpos,
            ))
            self.matches.append(Event(
                startpos=last.endpos,
                endpos=last.endpos,
                annot='-' + self.verbatim_type,
            ))

        return self.matches
    
    def add_opener(
        self,
        name: str,
        startpos: int,
        endpos: int,
        default_annot: str
    ):
        if name not in self.openers:
            self.openers[name] = []

        self.openers[name].append(
            Opener(
                match_index=len(self.matches),
                startpos=startpos,
                endpos=endpos,
                annot=None,
                sub_match_index=len(self.matches),
                substartpos=None,
                subendpos=None,
            )
        )

        self.add_match(startpos, endpos, default_annot)

    def clear_openers(self, startpos: int, endpos: int):
        # Remove all openers within the range.
        for k, v in self.openers.items():
            i = len(v) - 1 # last index
            # Here Python differs from JS implementation.
            # JS uses `while v[i]` which is fine when i goes out of range
            # as undefined will be returned.
            # In Python v[-1] will return the last element.
            while i >= 0: # last opener
                opener = v[i]
                # If opener falls into the range of startpos to endpos
                if opener.startpos >= startpos and opener.endpos <= endpos:
                    del v[i]
                elif (opener.substartpos and opener.substartpos >= startpos) and (opener.subendpos and opener.subendpos <= endpos):
                    # If opener substartps to subendpos falls into startpos and endpos
                    v[i].substartpos = None
                    v[i].subendpos = None
                    v[i].annot = None
                else:
                    break

                i -= 1

    def str_matches(self, startpos: int, endpos: int):
        i = len(self.matches) - 1
        while i > 0 and self.matches[i].startpos >= startpos:
            i -= 1

        if self.matches[i].startpos < startpos:
            i += 1

        while i < len(self.matches) and self.matches[i].endpos <= endpos:
            m = self.matches[i]
            if m.annot != 'escape' and m.annot != 'str':
                m.annot = 'str'

            i += 1

    def feed(self, startpos: int, endpos: int):
        # Position firstpos and endpos as far as possible.
        if self.firstpos == -1 or startpos < self.firstpos:
            self.firstpos = startpos
        
        if self.lastpos < endpos:
            self.lastpos = endpos

        pos = startpos
        while pos <= endpos:
            if self.attribute_parser is not None:
                sp = pos
                next_special = find_special(self.subject, pos, endpos)
                if next_special is None:
                    ep2 = endpos
                else:
                    ep2 = next_special

                result = self.attribute_parser.feed(sp, ep2)
                ep = result.position
                
                if result.is_done():
                    attribute_start = self.attribute_start
                    
                    if attribute_start is not None:
                        self.add_match(attribute_start, attribute_start, "+attributes")

                    attr_matches = self.attribute_parser.matches
                    for m in attr_matches:
                        self.add_match(m.startpos, m.endpos, m.annot)
                    self.add_match(ep, ep, "-attributes")

                    # restore state to prior to adding attribute parser
                    self.attribute_parser = None
                    self.attribute_start = None
                    self.attribute_slices = None
                    pos = ep + 1
                elif result.is_fail():
                    self.reparse_attributes()
                    pos = sp
                elif result.is_continue():
                    if self.attribute_slices is None:
                        self.attribute_slices = []
                    self.attribute_slices.append(
                        AttrSlice(
                            startpos=sp,
                            endpos=ep,
                        )
                    )
                    pos = ep + 1
            else:
                # Try to find the position of a special char.
                next_special = find_special(self.subject, pos, endpos)
                # If this is a single plain line.
                # newpos points to position after endpos,
                # or the position of the special char.
                if next_special is None:
                    newpos = endpos + 1
                else:
                    newpos = next_special

                # If pos is a special char itself, this will not be executed.
                if newpos > pos:
                    self.add_match(pos, newpos-1, 'str')
                    # Move pointer forward.
                    pos = newpos
                    # If we've reached the end of the line,
                    # we're done.
                    if pos > endpos:
                        break
                
                # Now we are pointing to a special character.
                c = ord(self.subject[pos])
                # JS version raised error here.
                # Python might not need it.

                # Current char is \r or \n
                if c == C_CR or c == C_LF:
                    # If we have a \r\n and reaching the endpos.
                    if c == C_CR and ord(self.subject[pos+1]) == C_LF and pos+1 <= endpos:
                        # In pargraph:
                        # Newlines are treated as soft breaks and 
                        # interpreted like spaces in formatted output.
                        # Line breaks in inline content are treated as “soft” breaks
                        self.add_match(pos, pos+1, 'soft_break')
                        pos = pos+2
                    else: # pos+1 > endpos. So pos must be equal to endpos.
                        self.add_match(pos, pos, 'hard_break')
                        pos = pos+1
                elif self.verbatim > 0: 
                    # verbatim is set by `handle_backtick` upon opening backtick.
                    if c == C_BACKTICK:
                        # Current char is closing backtick
                        # Find consecutive ` from curent position
                        # m.captures is empty since the regex has no capturing groups.
                        # Here the regex is r'`+', one or more backticks.
                        # Why two backtick patterns?
                        # Because if we are already in verbatim,
                        # we are expecting at least on backtick to close it.
                        m = find(self.subject, patt_backticks1, pos, endpos)
                        if m:
                            endchar = m.endpos
                            # Number of backticks should match.
                            if m.endpos - pos + 1 == self.verbatim:
                                # Raw block
                                # ```{=html}
                                # r'\{=[^\s{}`]+\}'
                                # But if this is closing marker, why check raw block attributes?
                                m2 = find(self.subject, patt_raw_attribute, endchar+1, endpos)
                                if m2 and self.verbatim_type == "verbatim":
                                    self.add_match(pos, endchar, '-'+self.verbatim_type) # closing verbatim
                                    self.add_match(m2.startpos, m2.endpos, "raw_format") #{=html}
                                    pos = m2.endpos + 1 # after }
                                else:
                                    self.add_match(pos, endchar, '-'+self.verbatim_type)
                                    pos = endchar + 1

                                self.verbatim = 0 # clear
                                self.verbatim_type = "verbatim"
                            else:
                                # Number not matching. Plain text.
                                self.add_match(pos, endchar, 'str')
                                pos = endchar + 1
                        else: # if current char is backtick, why should the match fail?
                            self.add_match(pos, endpos, 'str')
                            pos = endpos + 1
                    else: # in verbatim but current char is not backtick.
                        self.add_match(pos, pos, 'str')
                        pos = pos + 1
                else: # not newline, not in verbatim.
                    matcher = self.matchers[c]
                    if matcher:
                        res = matcher(self, pos, endpos)
                        if res is None:
                            pos = self.single_char(pos)
                        else:
                            pos = res
                    else:
                        pos = self.single_char(pos)

        return

MATCHERS: Dict[int, MatcherFn] = {
    C_BACKTICK: handle_backtick,
    C_BACKSLASH: handle_backslash,
    C_LESSTHAN: handle_lessthan,
    # H~2~O
    C_TILDE: make_between_matched('~', 'subscript', 'str', always_true),
    # 20^th^
    C_HAT: make_between_matched('^', 'superscript', 'str', always_true),
    C_UNDERSCORE: make_between_matched('_', 'emph', 'str', always_true),
    C_ASTERISK: make_between_matched('*', 'strong', 'str', always_true),
    C_PLUS: make_between_matched('+', 'insert', 'str', has_brace),
    C_EQUALS: make_between_matched('=', 'mark', 'str', has_brace),
    C_SINGLE_QUOTE: make_between_matched(
        "'",
        annotation="single_quoted",
        defaultmatch="right_single_quote",
        opentest=can_open_single_quote
    ),
    C_DOUBLE_QUOTE: make_between_matched(
        '"',
        annotation='double_quoted',
        defaultmatch='left_double_quote',
        opentest=always_true
    ),
    C_LEFT_BRACE: handle_left_brace,
    C_COLON: handle_colon,
    C_PERIOD: handle_period,
    C_LEFT_BRACKET: handle_left_bracket,
    C_RIGHT_BRACKET: handle_right_bracket,
    C_LEFT_PAREN: handle_left_paren,
    C_RIGHT_PAREN: handle_right_paren,
    C_HYPHEN: handle_hyphen,
}  
