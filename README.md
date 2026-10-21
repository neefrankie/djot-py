# djot-py

A Python library for parsing the light markup format [djot](https://github.com/jgm/djot).

This implementation is based on and modified from [djot.js](https://github.com/jgm/djot.js).

## Usage

```bash
pip install djot-py
```

## API

To parse text into an AST, call `parse`:

```python
from djot import parse

ast = parse("hi there\nfriend\n\nnew para")
```

To parse text into events:

```python
from djot import EventParser

text = "hello *world*\n\nfoo"

parser = EventParser(text)

# The parse method returns an iterator of events.
for event in parser.parse():
    print(event)
```

There are no rendering features available currently. Will be added in the future.

## Differences from Djot.js

- Comment is not supported yet.
- Multi-line attributes is not supported yet.

## My personal view on the above not-yet-implemented features

### Comment

Comment should not be mixed with attributes.

I hope there's a specific comment syntax in the future. For example, there could be two types of comments:

- Line comment appeared at the end of each line, using symbols like `%%`
- Block comment wrapped in `%%%`, similar to code block.

### Multi-line attributes

Djot.js current implementation to support multi-line attributes involves a lot of backtracing,
which is in direct conflict with the philosophy of djot. To support multi-line attributes,
there needs a fundamental change in the line-based parsing algorithm.

### List

This is not hard to implement. However, too much choices might introduce future ambiguity.
I prefere simplicity rather than feature-rich. For example, Typst style simply uses `-` and `+`. Leave styling to a renderer. And block attributes could be used to convey some basic styling information.

## Chunk-based Advancement

Djot.js adopt a strict line-based advancement. Traditional compiler adopts a character-based advancement.
Markup languages like djot/markdown fall into neither of them. Each parsing step might span a char, half a line,
or several lines. I call it chunk-based advancement. This idea might be already discussed in compiler theory.
I'm not sure since I haven't read enough theoretical books.