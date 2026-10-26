"""Removal of control, zero-width and bidirectional-override characters from untrusted text.

The code points are built with chr() on purpose: writing them literally would put invisible characters
in this source file.
"""

import re

_WHITESPACE_CONTROLS = (0x09, 0x0A, 0x0D)
_OTHER_CONTROLS = (*range(0x00, 0x09), 0x0B, 0x0C, *range(0x0E, 0x20), 0x7F)
_ZERO_WIDTH = (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF)
_BIDI = (*range(0x202A, 0x202F), *range(0x2066, 0x206A))


def _char_class(codes: tuple[int, ...]) -> re.Pattern[str]:
    return re.compile("[" + "".join(re.escape(chr(c)) for c in codes) + "]")


_KEEP_WHITESPACE = _char_class((*_OTHER_CONTROLS, *_ZERO_WIDTH, *_BIDI))
_STRIP_ALL = _char_class((*_WHITESPACE_CONTROLS, *_OTHER_CONTROLS, *_ZERO_WIDTH, *_BIDI))


def strip_controls(text: str, *, keep_whitespace: bool = True) -> str:
    """Drop invisible and directional-override characters; optionally keep tab, newline, carriage return."""
    return (_KEEP_WHITESPACE if keep_whitespace else _STRIP_ALL).sub("", text)
