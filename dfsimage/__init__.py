"""BBC Micro Acorn DFS floppy disk image maintenance package and command-line utility."""

import sys

if sys.version_info[0] != 3 or sys.version_info[1] < 8:
    raise ImportError("Module dfsimage requires Python version 3.8.")

# pylint: disable=wrong-import-position
from .misc import ValidationWarning, InfWarning, DFSWarning
from .sectors import Sectors
from .inf import Inf
from .entry import Entry
from .side import Side
from .image import Image
from .mmbfile import MMBFile
from .mmbentry import MMBEntry
from .cli import cli
from .enums import ListFormat, DigestMode, SizeOption, WarnMode
from .enums import InfMode, OpenMode, TranslationMode
from .enums import ListFormatUnion
from .pattern import ParsedPattern, PatternList
from .pattern import PatternUnion

__version__ = '0.9rc3'
VERSION = __version__

__all__ = ['Image', 'Side', 'Entry', 'Inf', 'Sectors', 'MMBFile', 'MMBEntry', 'cli',
           'ValidationWarning', 'InfWarning', 'DFSWarning',
           'ListFormat', 'DigestMode', 'SizeOption', 'WarnMode', 'InfMode', 'ListFormatUnion',
           'OpenMode', 'TranslationMode', 'ParsedPattern', 'PatternList', 'PatternUnion']
__author__ = "Tadek Kijkowski <tkijkowski@gmail.com>"
