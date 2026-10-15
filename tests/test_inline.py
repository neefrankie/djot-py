import unittest

from djot.event import (
    Event,
    InlineLeaf,
    VerbatimKind,
    InlineContainer,
    AttrKind,
    VerbatimKind
)
from djot.common import Range
from djot.input import InputText
from djot.inline.parser import InlineParser


class TestInlineParser(unittest.TestCase):

    def test_basic_parsing(self):
        text = 'hello there'

        parser = InlineParser(
            cursor=InputText(text),
        )

        parser.feed(0, 6)
        parser.feed(8, 10)

        expected = [
            Event.str(0, 6),
            Event.str(8, 10)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_verbatim(self):
        text = "x ``` hello ``there ``` x"
        #       0123456789012345678901234
        parser = InlineParser(
            cursor=InputText(text),
        )

        parser.feed(0, 24)

        expected = [
            Event.str(0, 1),
            Event.enter(Range(2, 4), VerbatimKind.VERBATIM),
            Event.str(5, 11),
            Event.str(12, 13),
            Event.str(14, 19),
            Event.exit(Range(20, 22), VerbatimKind.VERBATIM),
            Event.str(23, 24)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_parse_escaped(self):
        text = '\\"\\*\\ \\a \\\n'
        #        01 23 45 678 90
        parser = InlineParser(
            cursor=InputText(text),
            
        )
        parser.feed(0, 10)

        expected = [
            Event.escape(0, 0),
            Event.str(1, 1),
            Event.escape(2, 2),
            Event.str(3, 3),
            Event.escape(4, 4),
            Event.nbsp(5, 5),
            Event.str(6, 6),
            Event.str(7, 7),
            Event.escape(9, 9),
            Event.hardbreak(10, 10)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_parse_autolinks(self):
        parser = InlineParser(
            cursor=InputText('<http://example.com?foo=bar&baz=&amp;x2>'),
            
        )

        parser.feed(0, 39)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.URL),
            Event.str(1, 38),
            Event.exit(Range(39, 39), InlineContainer.URL),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_parse_email_autolinks(self):
            parser = InlineParser(
                cursor=InputText('<me@example.com>'),
                
            )
    
            parser.feed(0, 15)
    
            expected = [
                Event.enter(Range(0, 0), InlineContainer.EMAIL),
                Event.str(1, 14),
                Event.exit(Range(15, 15), InlineContainer.EMAIL),
            ]
    
            self.assertEqual(parser.state.get_matches(), expected)

    def test_super_subscript(self):
        parser = InlineParser(
            cursor=InputText('H~2~O e=mc^2^ test{^two words^}'),
            
        )

        parser.feed(0, 30)

        expected = [
             Event.str(0, 0),
             Event.enter(Range(1, 1), InlineContainer.SUBSCRIPT),
             Event.str(2, 2),
             Event.exit(Range(3, 3), InlineContainer.SUBSCRIPT),
             Event.str(4, 6),
             Event.str(7, 7),
             Event.str(8, 9),
             Event.enter(Range(10, 10), InlineContainer.SUPERSCRIPT),
             Event.str(11, 11),
             Event.exit(Range(12, 12), InlineContainer.SUPERSCRIPT),
             Event.str(13, 17),
             Event.leaf(Range(18, 18), InlineLeaf.OPEN_MARKER),
             Event.enter(Range(18, 19), InlineContainer.SUPERSCRIPT),
             Event.str(20, 28),
             Event.exit(Range(29, 30), InlineContainer.SUPERSCRIPT),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_emphasis(self):
        parser = InlineParser(
            cursor=InputText('_hello *there*_ world'),
            
        )

        parser.feed(0, 20)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.EMPH),
            Event.str(1, 6),
            Event.enter(Range(7, 7), InlineContainer.STRONG),
            Event.str(8, 12),
            Event.exit(Range(13, 13), InlineContainer.STRONG),
            Event.exit(Range(14, 14), InlineContainer.EMPH),
            Event.str(15, 20)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_mark(self):
        parser = InlineParser(
            cursor=InputText('{=hello=}'),
            
        )
        parser.feed(0, 8)
        expected = [
            Event.leaf(
                Range(0, 0),
                InlineLeaf.OPEN_MARKER
            ),
            Event.enter(Range(0, 1), InlineContainer.MARK),
            Event.str(2, 6),
            Event.exit(Range(7, 8), InlineContainer.MARK)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_inserted(self):
        parser = InlineParser(
            cursor=InputText('{+hello+}'),
            
        )
        parser.feed(0, 8)
        expected = [
            Event.leaf(
                Range(0, 0),
                InlineLeaf.OPEN_MARKER
            ),
            Event.enter(Range(0, 1), InlineContainer.INSERT),
            Event.str(2, 6),
            Event.exit(Range(7, 8), InlineContainer.INSERT)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_quoted(self):
        parser = InlineParser(
            cursor=InputText('"dog\'s breakfast"'),
            
        )

        parser.feed(0, 16)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.DOUBLE_QUOTED),
            Event.str(1, 3),
            Event.right_single_quote(4, 4),
            Event.str(5, 15),
            Event.exit(Range(16, 16), InlineContainer.DOUBLE_QUOTED),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_parse_attributes(self):
        parser = InlineParser(
            cursor=InputText('{#foo .bar baz="bim"}'),
            
        )

        parser.feed(0, 20)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.ATTR),
            Event.attr(Range(1, 1), AttrKind.ID_MARKER),
            Event.attr(Range(2, 4), AttrKind.ID),
            Event.attr(Range(5, 5), AttrKind.SPACE),
            Event.attr(Range(6, 6), AttrKind.CLASS_MARKER),
            Event.attr(Range(7, 9), AttrKind.CLASS),
            Event.attr(Range(10, 10), AttrKind.SPACE),
            Event.attr(Range(11, 13), AttrKind.KEY),
            Event.attr(Range(14, 14), AttrKind.EQUAL_MARKER),
            Event.attr(Range(15, 15), AttrKind.QUOTE_MARKER),
            Event.attr(Range(16, 18), AttrKind.VALUE),
            Event.attr(Range(19, 19), AttrKind.QUOTE_MARKER),
            Event.exit(Range(20, 20), InlineContainer.ATTR),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_spans(self):
        parser = InlineParser(
            cursor=InputText('[hi]{#foo .bar baz="bim"}'),
            
        )

        parser.feed(0, 24)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.SPAN),
            Event.str(1, 2),
            Event.exit(Range(3, 3), InlineContainer.SPAN),
            Event.enter(Range(4, 4), InlineContainer.ATTR),
            Event.attr(Range(5, 5), AttrKind.ID_MARKER),
            Event.attr(Range(6, 8), AttrKind.ID),
            Event.space(9, 9),
            Event.attr(Range(10, 10), AttrKind.CLASS_MARKER),
            Event.attr(
                Range(11, 13),
                AttrKind.CLASS
            ),
            Event.space(14, 14),
            Event.attr(
                Range(15, 17),
                AttrKind.KEY
            ),
            Event.attr(
                Range(18, 18),
                AttrKind.EQUAL_MARKER
            ),
            Event.attr(
                Range(19, 19),
                AttrKind.QUOTE_MARKER
            ),
            Event.attr(
                Range(20, 22),
                AttrKind.VALUE
            ),
            Event.attr(
                Range(23, 23),
                AttrKind.QUOTE_MARKER
            ),
            Event.exit(Range(24, 24), InlineContainer.ATTR),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_inline_links(self):
        parser = InlineParser(
            cursor=InputText('[foobar](url)'),
            
        )

        parser.feed(0, 12)

        expected = [
            Event.enter(
                span=Range(0, 0),
                kind=InlineContainer.LINK_TEXT,
            ),
            Event.str(1, 6),
            Event.exit(
                span=Range(7, 7),
                kind=InlineContainer.LINK_TEXT,
            ),
            Event.enter(
                span=Range(8, 8),
                kind=InlineContainer.DESTINATION,
            ),
            Event.str(9, 11),
            Event.exit(
                span=Range(12, 12),
                kind=InlineContainer.DESTINATION,
            ),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_refrence_links(self):
        parser = InlineParser(
            cursor=InputText('[foobar][1]'),
            #                 01234567890
        )

        parser.feed(0, 10)

        expected = [
            Event.enter(Range(0, 0), InlineContainer.LINK_TEXT),
            Event.str(1, 6),
            Event.exit(Range(7, 7), InlineContainer.LINK_TEXT),
            Event.enter(Range(8, 8), InlineContainer.REFERENCE),
            Event.str(9, 9),
            Event.exit(Range(10, 10), InlineContainer.REFERENCE)
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_inline_image(self):
        parser = InlineParser(
            cursor=InputText('![foobar](url)'),
            #                 01234567890123
        )
        parser.feed(0, 13)
        expected = [
            Event.leaf(Range(0, 0), InlineLeaf.IMAGE_MARKER),
            Event.enter(Range(1, 1), InlineContainer.IMAGE_TEXT),
            Event.str(2, 7),
            Event.exit(Range(8, 8), InlineContainer.IMAGE_TEXT),
            Event.enter(Range(9, 9), InlineContainer.DESTINATION),
            Event.str(10, 12),
            Event.exit(Range(13, 13), InlineContainer.DESTINATION),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_symbs(self):
        parser = InlineParser(
            cursor=InputText(':+1:'),
            
        )

        parser.feed(0, 3)

        expected = [
            Event.leaf(Range(0, 3), InlineLeaf.SYMBOL),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_ellipses(self):
        parser = InlineParser(
            cursor=InputText('...'),
            
        )

        parser.feed(0, 2)

        expected = [
            Event.leaf(Range(0, 2), InlineLeaf.ELLIPSES),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_dashes(self):
        parser = InlineParser(
            cursor=InputText('a---b--c'),
            
        )
        parser.feed(0, 7)

        expected = [
            Event.str(0, 0),
            Event.leaf(Range(1, 3), InlineLeaf.EM_DASH),
            Event.str(4, 4),
            Event.leaf(Range(5, 6), InlineLeaf.EN_DASH),
            Event.str(7, 7),
        ]

        self.assertEqual(parser.state.get_matches(), expected)

    def test_note_reference(self):
        parser = InlineParser(
            cursor=InputText('[^ref]'),
            
        )

        parser.feed(0, 5)

        expected = [
            Event.leaf(Range(0, 5), InlineLeaf.FOOTNOTE_REF)
        ]

        self.assertEqual(parser.state.get_matches(), expected)






if __name__ == '__main__':
    unittest.main()