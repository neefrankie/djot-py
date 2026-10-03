# djot-py

Djot implementation in Python based on [djot.js](https://github.com/jgm/djot.js).

This is a work in progress.

## My Disagreement with Djot Philosophy

Rational:

These issues is in direct conflict with Djot's claimed principles.

### Comment

Comment should not be mixed with attributes.

There could be two types of comments:

- Line comment appeared at the end of each line, using symbols like `%%`
- Block comment wrapped in `%%%`, similar to code block.

### Multi-line attributes

This is left for futher consideration.

### List

There are two many styles in Djot list.

I prefer Typst style: just `-` and `+`. Leave styling to a renderer.

If you really want to specify how a list should look like,  attributes in front of a list block is suffice.