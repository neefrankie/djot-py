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

## Explicitly closed element vs implicitly closed element

Most block elements in djot (and also Markdown) are impplicitly closed elements.
They are not closed until a new element is visible.
That's the purpose of the `close` callback method,
passively closing previous elements.
There are a few exceptoions, however, like fenced div and code block.
Those elements are expclitly close with closing markup.
Their presence interrupted the meaning of `open`, `continue` and `close` workflow.
Those elements deserve special treatment.

In the test file block.spec.ts, there is an extra event `{ startpos: 24, endpos: 24, annot: "blankline" }` on line 246.
It is the position of newline char after ending colon:

```djot
::: warning

::: <- Here
```

In my view it should not be treated as a blankline.
This newline is undefined in Djot syntax.

Let's figure out why there is a trailing blankline.
When djot.js sees the ending `:::`, its continue method returns
`false`, and set cursor to `\r` if it exists, otherwise `\n`.
So the check continuations loops stops before this container.
When it comes to open stage, no rule works for current cursor
position which is the the return or newline char.
Since it is not lazy content, the container is closed.
Then it falls into `tip.content === ContentType.Block` and `isBlank`
branch, which creates a blankline event for the trailing return or newline char.

A improved approach should close the container at checking continuations step and jump to next line directly.
Fenced div is a explicitly closed element. There's no neeed to let it falltrough.
