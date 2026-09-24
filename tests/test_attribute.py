import unittest

from djot.attributes import (
    AttributeParser,
    State,
    AttrFlowControl,
    AttrKind,
    AttrParseResult,
)
from djot.input import InputText
from djot.event import Event, AttrKind
from djot.common import Range

class TestAttributeState(unittest.TestCase):
    def test_start(self):
        cases = [
            (' ', State.FAIL),
            ('{', State.SCANNING),
        ]

        for text, expected in cases:
            with self.subTest():
                parser = AttributeParser(InputText(text))
                actual = parser._start(0)
                self.assertEqual(actual, expected)

    def test_scanning(self):
        cases = [
            (' ', State.SCANNING),
            ('\t', State.SCANNING),
            ('}', State.DONE),
            ('#', State.SCANNING_ID),
            ('.', State.SCANNING_CLASS),
            ('key', State.SCANNING_KEY),
            ('\n', State.FAIL)
        ]

        for text, expected in cases:
            with self.subTest():
                parser = AttributeParser(InputText(text))
                actual = parser._scanning(0)
                self.assertEqual(actual, expected)

    def test_scanning_id(self):
        cases = [
            ('ident_1', State.SCANNING_ID),
            ('}', State.DONE),
            (' ', State.SCANNING),
            ('.', State.FAIL),
            ('\n', State.FAIL)
        ]
        for text, expected in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))
                actual = parser._scanning_id(0)
                self.assertEqual(actual, expected)

    def test_scanning_class(self):
        cases = [
            ('dark', State.SCANNING_CLASS),
            ('}', State.DONE),
            (' ', State.SCANNING),
            ('.', State.FAIL),
            ('\n', State.FAIL)
        ]
        for text, expected in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))
                actual = parser._scanning_class(0)
                self.assertEqual(actual, expected)

    def test_scanning_key(self):
        cases = [
            ('=', State.SCANNING_VALUE),
            ('key', State.SCANNING_KEY),
            (' ', State.FAIL),
            ('.', State.FAIL),
            ('\n', State.FAIL)
        ]
        for text, expected in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))
                parser.begin = 1
                parser.lastpos = 2
                actual = parser._scanning_key(0)
                self.assertEqual(actual, expected)
    def test_scanning_value(self):
        cases = [
            ('"', State.SCANNING_QUOTED_VALUE),
            ('value', State.SCANNING_BARE_VALUE),
            (' ', State.FAIL),
            ('.', State.FAIL),
            ('\n', State.FAIL)
        ]
        for text, expected in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))
                actual = parser._scanning_value(0)
                self.assertEqual(actual, expected)

    def test_scanning_bare_value(self):
        cases = [
            ('value', State.SCANNING_BARE_VALUE),
            ('}', State.DONE),
            (' ', State.SCANNING),
            ('\n', State.FAIL)
        ]
        for text, expected in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))
                parser.begin = 1
                parser.lastpos = 2
                actual = parser._scanning_bare_value(0)
                self.assertEqual(actual, expected)

    def test_scanning_quoted_value(self):
        cases = [
            ('"', State.SCANNING),
            ('\\', State.SCANNING_ESCAPED),
            (' ', State.SCANNING_QUOTED_VALUE),
            ('\n', State.FAIL)
        ]
        for text, expected in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))
                parser.begin = 1
                parser.lastpos = 2
                actual = parser._scanning_quoted_value(0)
                self.assertEqual(actual, expected)

class TestAttributeParser(unittest.TestCase):
    def test_step(self):
        cases = [
            (
                '{#ident}',
                [
                    State.SCANNING,
                    State.SCANNING_ID,
                    State.SCANNING_ID,
                    State.SCANNING_ID,
                    State.SCANNING_ID,
                    State.SCANNING_ID,
                    State.SCANNING_ID,
                    State.DONE,
                ]
            ),
            (
                '{.dark}',
                [
                    State.SCANNING,
                    State.SCANNING_CLASS,
                    State.SCANNING_CLASS,
                    State.SCANNING_CLASS,
                    State.SCANNING_CLASS,
                    State.SCANNING_CLASS,
                    State.DONE,
                ]
            ),
            (
                '{key=value}',
                [
                    State.SCANNING,
                    State.SCANNING_KEY,
                    State.SCANNING_KEY,
                    State.SCANNING_KEY,
                    State.SCANNING_VALUE,
                    State.SCANNING_BARE_VALUE,
                    State.SCANNING_BARE_VALUE,
                    State.SCANNING_BARE_VALUE,
                    State.SCANNING_BARE_VALUE,
                    State.SCANNING_BARE_VALUE,
                    State.DONE,
                ]
            ),
            (
                '{a-b="a b"}',
                [
                    State.SCANNING,
                    State.SCANNING_KEY,
                    State.SCANNING_KEY,
                    State.SCANNING_KEY,
                    State.SCANNING_VALUE,
                    State.SCANNING_QUOTED_VALUE,
                    State.SCANNING_QUOTED_VALUE,
                    State.SCANNING_QUOTED_VALUE,
                    State.SCANNING_QUOTED_VALUE,
                    State.SCANNING,
                    State.DONE,
                ]
            )
        ]

        for text, states in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))

                actual = parser.state
                for i, expected in enumerate(states):
                    actual = parser.step(actual, i)
                    
                    self.assertEqual(actual, expected)
                    parser.lastpos = i

    def test_feed(self):
        cases = [
            (
                '{#ident .dark key=value}',
                [
                    Event.attr(Range(1, 1), AttrKind.ID_START),
                    Event.attr(Range(2, 6), AttrKind.ID),
                    Event.attr(Range(7, 7), AttrKind.SPACE),
                    Event.attr(Range(8, 8), AttrKind.CLASS_START),
                    Event.attr(Range(9, 12), AttrKind.CLASS),
                    Event.attr(Range(13, 13), AttrKind.SPACE),
                    Event.attr(Range(14, 16), AttrKind.KEY),
                    Event.attr(Range(17, 17), AttrKind.EQUAL_MARKER),
                    Event.attr(Range(18, 22), AttrKind.VALUE),
                ],
                AttrParseResult(
                    status=AttrFlowControl.DONE,
                    position=23,
                )
            ),
        ]

        for text, expected_events, expected_result in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))
                actual_result = parser.feed(0, len(text)-1)
                self.assertEqual(len(parser.events), len(expected_events))
                self.assertEqual(actual_result, expected_result)

                for i, actual in enumerate(parser.events):
                    self.assertEqual(actual, expected_events[i])
                    

    def test_failure(self):

        cases = [
            ('{#ident .dark key=value', AttrParseResult(AttrFlowControl.FAIL, position=23)),
            ('{#ident .dark key="no closing quote}', AttrParseResult(AttrFlowControl.FAIL, position=36))
        ]

        for text, expected in cases:
            with self.subTest(text):
                parser = AttributeParser(InputText(text))
                actual = parser.feed(0, len(text)-1)
                self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()