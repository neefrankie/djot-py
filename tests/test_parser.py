import unittest

from djot.ast import (
    Doc,
    Para,
    Str,
    SoftBreak,
    AstNode,
    HasChildren
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


if __name__ == '__main__':
    unittest.main()