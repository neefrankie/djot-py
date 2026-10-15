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
)
from djot.common import (
    Pos,
    SourceLoc,
    Alignment,
)
from djot.parser import (
    parse,
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

    
if __name__ == '__main__':
    unittest.main()