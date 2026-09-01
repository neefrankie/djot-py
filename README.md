# Pyjot

Djot implementation in Python.

This is a work in progress.

## Architecture

1. Parse a string into an array of Events with `parse_events` in `pyjot/block.py`
2. The Events stream is parsed into AST by `parse()` in `pyjot/parse.py`

## EventParser

┌─────────────────────────────────────────────────────────┐
│                    EventParser                          │
├─────────────────────────────────────────────────────────┤
│  1. 文本管理    │  2. 位置管理    │  3. 容器管理    │
│  - subject      │  - pos          │  - containers   │
│  - maxoffset    │  - indent       │  - tip()        │
│                 │  - startline    │  - add_container│
│                 │  - starteol     │  - close_...    │
│                 │  - endeol       │                 │
├─────────────────────────────────────────────────────────┤
│  4. 块匹配器    │  5. 行内解析    │  6. 事件生成    │
│  - _open_*      │  - InlineParser │  - matches      │
│  - _continue_*  │  - get_inline_  │  - add_match    │
│  - _close_*     │    matches()    │  - __iter__     │
├─────────────────────────────────────────────────────────┤
│  7. 特殊处理    │  8. 工具方法                         │
│  - parse_table  │  - find()                           │
│  - parse_cell   │  - skip_space()                     │
│                 │  - get_eol()                        │
└─────────────────────────────────────────────────────────┘