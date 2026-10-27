import unittest

from djot.attributes import (
    AttributeParser,
    AttrStatus,
    AttrKind,
)
from djot.cursor import Cursor
from djot.event import Event, AttrKind
from djot.common import Range

class TestAttributeParser(unittest.TestCase):
    def test_parse_attributes(self):
        x = '''
{a=b #ident
.class
key=val1
.class key2="val two \\" ok"}abc
'''.strip()

        parser = AttributeParser(Cursor(x))
        result = parser.feed(0, len(x)-1)
        self.assertEqual(result.position, 55)
        self.assertEqual(result.status, AttrStatus.DONE)

        expected = [
            Event.attr(Range(1, 1), AttrKind.KEY),
            Event.attr(Range(2, 2), AttrKind.EQUAL_MARKER),
            Event.attr(Range(3, 3), AttrKind.VALUE),
            Event.attr(Range(4, 4), AttrKind.SPACE),
            Event.attr(Range(5, 5), AttrKind.ID_MARKER),
            Event.attr(Range(6, 10), AttrKind.ID),
            Event.attr(Range(12, 12), AttrKind.CLASS_MARKER),
            Event.attr(Range(13, 17), AttrKind.CLASS),
            Event.attr(Range(19, 21), AttrKind.KEY),
            Event.attr(Range(22, 22), AttrKind.EQUAL_MARKER),
            Event.attr(Range(23, 26), AttrKind.VALUE),
            Event.attr(Range(28, 28), AttrKind.CLASS_MARKER),
            Event.attr(Range(29, 33), AttrKind.CLASS),
            Event.attr(Range(34, 34), AttrKind.SPACE),
            Event.attr(Range(35, 38), AttrKind.KEY),
            Event.attr(Range(39, 39), AttrKind.EQUAL_MARKER),
            Event.attr(Range(40, 40), AttrKind.QUOTE_MARKER),
            Event.attr(Range(41, 53), AttrKind.VALUE),
            Event.attr(Range(54, 54), AttrKind.QUOTE_MARKER),
        ]

        self.assertEqual(parser.events, expected)



if __name__ == '__main__':
    unittest.main()