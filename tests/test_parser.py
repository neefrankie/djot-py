import unittest

from djot.ast import (
    Doc,
    Para,
    Str,
    SoftBreak,
    AstNode,
    HasChildren,
    Heading,
    BlockQuote,
    Emph,
    Reference,
    Table,
    Row,
    Cell,
    Caption,
    CodeBlock,
    BulletList,
    BulletListStyle,
    ListItem,
    OrderedList,
    OrderedListStyle,
    DefinitionList,
    Term,
    Definition,
    DefinitionListItem,
    ThematicBreak,
    Div,
    Footnote,
    Verbatim,
    NonBreakingSpace,
    HardBreak,
    Url,
    Email,
    Subscript,
    Superscript,
    Strong,
    Mark,
    Insert,
    DoubleQuoted,
    SmartPunctuation,
    SmartPunctType,
    Span,
    Link,
    Image,
    Symb,
    FootnoteReference,
)
from djot.common import (
    Pos,
    SourceLoc,
    Alignment,
)
from djot.parser import (
    parse,
    render_ast,
)

def iter_node(node: AstNode):
    yield node
    if isinstance(node, HasChildren):
        for child in node.children:
            yield from iter_node(child)
    elif isinstance(node, DefinitionListItem):
        yield from iter_node(node.term)
        yield from iter_node(node.definition)


class TestParser(unittest.TestCase):
    def test_para(self):
        ast = parse("hi there\nfriend\n\nnew para")
        #            012345678 9012345 6 78901234

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Str(text="hi there"),
                        SoftBreak(),
                        Str(text="friend")
                    ]
                ),
                Para(
                    children=[
                        Str(text="new para")
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_blockquote(self):
        ast = parse("> hello\n> there\nlazy\n>\n> hi\n")
        #            01234567 89012345 67890 12 34567

        expected = Doc(
            references={},
            footnotes={},
            children=[
                BlockQuote(
                    children=[
                        Para(
                            children=[
                                Str(text='hello'),
                                SoftBreak(),
                                Str(text='there'),
                                SoftBreak(),
                                Str(text='lazy')
                            ]
                        ),
                        Para(
                            children=[
                                Str(text='hi')
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_heading(self):
        ast = parse("## hello\n## there\nlazy\n")
        #            012345678 901234567 89012

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Heading(
                    level=2,
                    children=[
                        Str(text='hello'),
                        SoftBreak(),
                        Str(text='there'),
                        SoftBreak(),
                        Str(text='lazy')
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_reference_definition(self):
        ast = parse("[foo]: bar\n baz\n")

        expected = Doc(
            references={
                'foo': Reference(
                    label='foo',
                    destination='barbaz',
                )
            },
            footnotes={},
            children=[]
        )

        self.assertEqual(ast, expected)

    def test_table(self):
        ast = parse("| a | b |\n|--|--:|\n|33|2| ")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Table(
                    caption=Caption(
                        children=[]
                    ),
                    children=[
                        Row(
                            head=True,
                            children=[
                                Cell(
                                    head=True,
                                    children=[
                                        Str(text='a')
                                    ],
                                    align=Alignment.DEFAULT,
                                ),
                                Cell(
                                    head=True,
                                    children=[
                                        Str(text='b')
                                    ],
                                    align=Alignment.RIGHT,
                                )
                            ]
                        ),
                        Row(
                            head=False,
                            children=[
                                Cell(
                                    head=False,
                                    children=[
                                        Str(text='33')
                                    ],
                                    align=Alignment.DEFAULT,
                                ),
                                Cell(
                                    head=False,
                                    children=[
                                        Str(text='2')
                                    ],
                                    align=Alignment.RIGHT,
                                )
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_caption(self):
        ast = parse("| a | b |\n\n^ caption")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Table(
                    caption=Caption(
                        children=[
                            Str(text='caption')
                        ]
                    ),
                    children=[
                        Row(
                            head=False,
                            children=[
                                Cell(
                                    head=False,
                                    children=[
                                        Str(text='a')
                                    ],
                                    align=Alignment.DEFAULT,
                                ),
                                Cell(
                                    head=False,
                                    children=[
                                        Str(text='b')
                                    ],
                                    align=Alignment.DEFAULT,
                                )
                            ]
                        ),
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_code_block(self):
        ast = parse("```` python\nif x == 3:\n  y = 4\n````\n")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                CodeBlock(
                    lang='python',
                    text="if x == 3:\n  y = 4\n"
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_list(self):
        ast = parse("- one\n- two")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                BulletList(
                    style=BulletListStyle.DASH,
                    children=[
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text='one')
                                    ]
                                ),
                            ]
                        ),
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text='two')
                                    ]
                                )
                            ]
                        )
                    ],
                    loose=False
                ),
            ]
        )

        self.assertEqual(ast, expected)

    def test_list_loose(self):
        ast = parse("- one\n\n- two")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                BulletList(
                    style=BulletListStyle.DASH,
                    children=[
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text='one')
                                    ]
                                ),
                            ]
                        ),
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text='two')
                                    ]
                                )
                            ]
                        )
                    ],
                    loose=True
                ),
            ]
        )

        self.assertEqual(ast, expected)

    def test_list_multi_line(self):
        """
        +LIST
            +LIST_ITEM
                +PARA
                    STR
                -PARA
                BLANKLINE
                +PARA
                    STR
                -PARA
            -LIST_ITEM
        -LIST
        """
        ast = parse("- one\n\n  two")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                BulletList(
                    style=BulletListStyle.DASH,
                    children=[
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text='one')
                                    ]
                                ),
                                Para(
                                    children=[
                                        Str(text='two')
                                    ]
                                )
                            ]
                        ),
                    ],
                    loose=True
                ),
            ]
        )

        self.assertEqual(ast, expected)

    def test_list_items(self):
        ast = parse("- one\n- two\n1. three\n(iv) four\n\n - sub\n\n   two\n")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                BulletList(
                    style=BulletListStyle.DASH,
                    children=[
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text='one')
                                    ]
                                ),
                            ]
                        ),
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text='two')
                                    ]
                                )
                            ]
                        )
                    ],
                    loose=False
                ),
                OrderedList(
                    style=OrderedListStyle.NUMBER,
                    children=[
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text="three")
                                    ]
                                )
                            ]
                        )
                    ],
                    loose=False,
                    start=1,
                ),
                OrderedList(
                    style=OrderedListStyle.LOWER_ROMAN_PAREN,
                    children=[
                        ListItem(
                            children=[
                                Para(
                                    children=[
                                        Str(text="four")
                                    ]
                                ),
                                BulletList(
                                    style=BulletListStyle.DASH,
                                    children=[
                                        ListItem(
                                            children=[
                                                Para(
                                                    children=[
                                                        Str(text="sub")
                                                    ]
                                                ),
                                                Para(
                                                    children=[
                                                        Str(text="two")
                                                    ]
                                                )
                                            ]
                                        )
                                    ],
                                    loose=True
                                )
                            ]
                        )
                    ],
                    loose=True,
                    start=4,
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_definition_list(self):
        ast = parse(": orange\n\n  A citrus fruit.\n")
        expected = Doc(
            references={},
            footnotes={},
            children=[
                DefinitionList(
                    children=[
                        DefinitionListItem(
                            term=Term(
                                children=[
                                    Str(text='orange')
                                ]
                            ),
                            definition=Definition(
                                children=[
                                    Para(
                                        children=[
                                            Str(text='A citrus fruit.')
                                        ]
                                    )
                                ]
                            )
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_thematic_break(self):
        ast = parse(" - - - -\n")
        expected = Doc(
            references={},
            footnotes={},
            children=[
                ThematicBreak()
            ]
        )
        self.assertEqual(ast, expected)

    def test_fenced_div(self):
        ast = parse(":::: foo \nhello\n\nhi\n::::")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Div(
                    attributes={'class': 'foo'},
                    children=[
                        Para(
                            children=[
                                Str(text='hello'),
                            ]
                        ),
                        Para(
                            children=[
                                Str(text='hi')
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_footnotes(self):
        ast = parse("[^note]: This is a\nnote\n\n  second par\n\nafter note\n")
        expected = Doc(
            references={},
            footnotes={
                'note': Footnote(
                    children=[
                        Para(
                            children=[
                                Str(text='This is a')
                            ]
                        ),
                        Para(
                            children=[
                                Str(text='note')
                            ]
                        ),
                        Para(
                            children=[
                                Str(text='second par')
                            ]
                        ),
                        Para(
                            children=[
                                Str(text='after note')
                            ]
                        )
                    ],
                    label='note',
                )
            },
            children=[],
        )

    def test_verbatim(self):
        ast = parse("x ``` hello ``there ``` x")

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Str(text='x '),
                        Verbatim(
                            text=' hello ``there '
                        ),
                        Str(text=' x')
                    ]
                ),
            ]
        )

        self.assertEqual(ast, expected)

    def test_escaped(self):
        ast = parse('\\"\\*\\ \\a \\\n')
        #             01 23 45 678 90
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Str(text='"'),
                        Str(text='*'),
                        NonBreakingSpace(),
                        Str(text='\\a'),
                        HardBreak(),
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_autolink(self):
        ast = parse('<http://example.com?foo=bar&baz=&amp;x2>')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Url(
                            text='http://example.com?foo=bar&baz=&amp;x2'
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_auto_email(self):
        ast = parse('<me@example.com>')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Email(
                            text='me@example.com'
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_super_sub(self):
        ast = parse('H~2~O e=mc^2^')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Str(text='H'),
                        Subscript(
                            children=[
                                Str(text='2')
                            ]
                        ),
                        Str(text='O e=mc'),
                        Superscript(
                            children=[
                                Str(text='2')
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_emphasis(self):
        ast = parse('_hello *there*_ world')
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Emph(
                            children=[
                                Str(text='hello '),
                                Strong(
                                    children=[
                                        Str(text='there')
                                    ]
                                ),
                            ]
                        ),
                        Str(text=' world')
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_mark(self):
        ast = parse('{=hello=}')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Mark(
                            children=[
                                Str(text='hello')
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_insert(self):
        ast = parse('{+hello+}')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Insert(
                            children=[
                                Str(text='hello')
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_quoted(self):
        ast = parse('"dog\'s breakfast"')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        DoubleQuoted(
                            children=[
                                Str(text='dog'),
                                SmartPunctuation(
                                    text="'",
                                    type=SmartPunctType.RIGHT_SINGLE_QUOTE,
                                ),
                                Str(text='s breakfast')
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_span(self):
        ast = parse('[hi]{#foo .bar baz="bim"}')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Span(
                            attributes={
                                'id': 'foo',
                                'class': 'bar',
                                'baz': 'bim'
                            },
                            children=[
                                Str(text='hi')
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_inline_links(self):
        ast = parse('[foobar](url)')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Link(
                            children=[
                                Str(text='foobar')
                            ],
                            destination='url',
                            reference=None
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_reference_links(self):
        ast = parse('[foobar][1]')
        
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Link(
                            children=[
                                Str(text='foobar')
                            ],
                            destination=None,
                            reference='1'
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_inline_image(self):
        ast = parse('![foobar](url)')
        
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Image(
                            children=[
                                Str(text='foobar')
                            ],
                            destination='url',
                            reference=None,
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_symb(self):
        ast = parse(':+1:')
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Symb(
                            alias='+1'
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_ellipse(self):
        ast = parse('...')
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        SmartPunctuation(
                            text='...',
                            type=SmartPunctType.ELLIPSES
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_dash(self):
        ast = parse('a---b--c')
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        Str(text='a'),
                        SmartPunctuation(
                            text='---',
                            type=SmartPunctType.EM_DASH
                        ),
                        Str(text='b'),
                        SmartPunctuation(
                            text='--',
                            type=SmartPunctType.EN_DASH
                        ),
                        Str(text='c'),
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_note_reference(self):
        ast = parse('[^ref]')

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    children=[
                        FootnoteReference(
                            text='ref'
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)


    def test_block_attributes(self):
        ast = parse("{.foo}\n{#bar .baz}\nHello")
        #            0123456 789012345678 90123

        expected = Doc(
            references={},
            footnotes={},
            children=[
                Para(
                    attributes={
                        'class': 'foo baz',
                        'id': 'bar'
                    },
                    children=[
                        Str(text='Hello')
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    

    
    def test_source_position(self):
        """
        +HEADING(0)
            STR(2, 8)
        -HEADING(9)
        BLANKLINE(10)
        +BLOCKQUOTE(11)
            +PARA(13)
                STR(13, 20)
                +EMPH(21)
                    STR(22, 28)
                -EMPH(29)
            -PARA(30) this is railing line added during normalization
        -BLOCKQUOTE(31)
        """
        ast = parse("# testing\n\n> testing _testing_", True)
        #            0123456789 0 1234567890123456789
        # 
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Heading(
                    level=1,
                    pos=Pos(
                        start=SourceLoc(
                            line=1,
                            col=1,
                            offset=0,
                        ),
                        end=SourceLoc(
                            line=1,
                            col=10,
                            offset=9,
                        )
                    ),
                    children=[
                        Str(
                            text='testing',
                            pos=Pos(
                                start=SourceLoc(
                                    line=1,
                                    col=3,
                                    offset=2,
                                ),
                                end=SourceLoc(
                                    line=1,
                                    col=9,
                                    offset=8,
                                )
                            )
                        )
                    ]
                ),
                BlockQuote(
                    pos=Pos(
                        start=SourceLoc(
                            line=3,
                            col=1,
                            offset=11,
                        ),
                        end=SourceLoc(
                            line=3,
                            col=20,
                            offset=30,
                        )
                    ),
                    children=[
                        Para(
                            pos=Pos(
                                start=SourceLoc(
                                    line=3,
                                    col=3,
                                    offset=13,
                                ),
                                end=SourceLoc(
                                    line=3,
                                    col=20,
                                    offset=30,
                                )
                            ),
                            children=[
                                Str(
                                    text='testing ',
                                    pos=Pos(
                                        start=SourceLoc(
                                            line=3,
                                            col=3,
                                            offset=13,
                                        ),
                                        end=SourceLoc(
                                            line=3,
                                            col=10,
                                            offset=20,
                                        )
                                    )
                                ),
                                Emph(
                                    pos=Pos(
                                        start=SourceLoc(
                                            line=3,
                                            col=11,
                                            offset=21,
                                        ),
                                        end=SourceLoc(
                                            line=3,
                                            col=19,
                                            offset=29
                                        )
                                    ),
                                    children=[
                                        Str(
                                            text="testing",
                                            pos=Pos(
                                                start=SourceLoc(
                                                    line=3,
                                                    col=12,
                                                    offset=22,
                                                ),
                                                end=SourceLoc(
                                                    line=3,
                                                    col=18,
                                                    offset=28,
                                                )
                                            )
                                        )
                                    ]
                                )
                            ]
                        )
                    ]
                )
            ]
        )

        self.assertEqual(ast, expected)

    def test_render_pretty(self):
        ast = parse("hi there\nfriend\n\nnew para\n", source_positions=True)
        #            012345678 9012345 6 789012345

        actual = render_ast(ast)

        expected = """doc
  para (1:1:0-2:7:15)
    str (1:1:0-1:8:7) text="hi there"
    soft_break (1:9:8-1:9:8)
    str (2:1:9-2:6:14) text="friend"
  para (4:1:17-4:9:25)
    str (4:1:17-4:8:24) text="new para"
"""

        self.assertEqual(actual, expected)



    
if __name__ == '__main__':
    unittest.main()