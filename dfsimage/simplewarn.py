"""Simple warnings module.

All warnings go to sys.stderr, no line numbers or stack frames.
Warnings can be muted and unmuted globally by type.
Format can be changed globally.
"""

import sys
from typing import Set, Type, IO, Callable

muted: Set[Type] = set()
stderr: IO = sys.stderr


def formatmsg(message) -> str:
    """Format message."""
    return "%s: %s" % (type(message).__name__, str(message))


current_format: Callable = formatmsg


def warn(message):
    """Warnings just go out to stderr."""
    for typ in muted:
        if isinstance(message, typ):
            return
    print(current_format(message), file=stderr)


def mute(typ: Type):
    """Mute warning class."""
    muted.add(typ)


def unmute(typ: Type):
    """Unmute warning class."""
    muted.discard(typ)
