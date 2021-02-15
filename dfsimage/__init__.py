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
from .consts import LIST_FORMAT_RAW, LIST_FORMAT_INFO, LIST_FORMAT_INF, LIST_FORMAT_CAT
from .consts import LIST_FORMAT_JSON, LIST_FORMAT_XML, LIST_FORMAT_TABLE, LIST_FORMAT_DCAT
from .consts import DIGEST_MODE_ALL, DIGEST_MODE_USED, DIGEST_MODE_FILE, DIGEST_MODE_DATA
from .consts import SIZE_OPTION_KEEP, SIZE_OPTION_EXPAND, SIZE_OPTION_SHRINK
from .consts import WARN_FIRST, WARN_NONE, WARN_ALL
from .consts import INF_MODE_ALWAYS, INF_MODE_AUTO, INF_MODE_NEVER
from .consts import TRANSLATION_STANDARD, TRANSLATION_SAFE

__version__ = '0.9rc2'
VERSION = __version__

__all__ = ['Image', 'Side', 'Entry', 'Inf', 'Sectors', 'MMBFile', 'MMBEntry', 'cli',
           'ValidationWarning', 'InfWarning', 'DFSWarning',
           'LIST_FORMAT_RAW', 'LIST_FORMAT_INFO', 'LIST_FORMAT_INF', 'LIST_FORMAT_CAT',
           'LIST_FORMAT_JSON', 'LIST_FORMAT_XML', 'LIST_FORMAT_TABLE', 'LIST_FORMAT_DCAT',
           'DIGEST_MODE_ALL', 'DIGEST_MODE_USED', 'DIGEST_MODE_FILE', 'DIGEST_MODE_DATA',
           'SIZE_OPTION_KEEP', 'SIZE_OPTION_EXPAND', 'SIZE_OPTION_SHRINK',
           'WARN_FIRST', 'WARN_NONE', 'WARN_ALL',
           'INF_MODE_ALWAYS', 'INF_MODE_AUTO', 'INF_MODE_NEVER',
           'TRANSLATION_STANDARD', 'TRANSLATION_SAFE']
__author__ = "Tadek Kijkowski <tkijkowski@gmail.com>"
