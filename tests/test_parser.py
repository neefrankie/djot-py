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
)
from djot.common import (
    Pos,
    SourceLoc
)
from djot.parser import (
    parse,
)

def iter_node(node: AstNode):
    yield node
    if isinstance(node, HasChildren):
        for child in node.children:
            yield from iter_node(child)


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

    def test_source_position(self):
        ast = parse("# testing\n\n> testing _testing_", True)
        #            0123456789 0 1234567890123456789
        expected = Doc(
            references={},
            footnotes={},
            children=[
                Heading(
                    level=1,
                    pos=Pos(
                        start=SourceLoc(
                            col=1,
                            line=1,
                            offset=0,
                        ),
                        end=SourceLoc(
                            col=0,
                            line=2,
                            offset=9,
                        )
                    ),
                    children=[
                        Str(
                            text='testing',
                            pos=Pos(
                                start=SourceLoc(
                                    col=3,
                                    line=1,
                                    offset=2,
                                ),
                                end=SourceLoc(
                                    col=9,
                                    line=1,
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

    
if __name__ == '__main__':
    unittest.main()