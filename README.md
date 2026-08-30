# Pyjot

Djot implementation in Python.

This is a work in progress.

## Architecture

1. Parse a string into an array of Events with `parse_events` in `pyjot/block.py`
2. The Events stream is parsed into AST by `parse()` in `pyjot/parse.py`