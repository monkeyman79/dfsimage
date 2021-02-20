"""Common enums and constants for the package."""

from enum import Enum
from typing import Union


class ListFormat(Enum):
    """Listing format."""

    #: List file names, no header.
    RAW = 0
    #: As displayed by ``*INFO`` command.
    INFO = 1
    #: As in ``.inf`` files.
    INF = 2
    #: As displayed by ``*CAT`` command.
    CAT = 3
    #: Generate ``JSON``
    JSON = 4
    #: Generate ``XML``
    XML = 5
    #: Fixed-width text table.
    TABLE = 6
    #: As displayed by MMC ``*DCAT`` command.
    DCAT = 7


#: Format parameter type - either one of :class:`ListFormat` or a custom string.
ListFormatUnion = Union[ListFormat, str]


class DigestMode(Enum):
    """Digest mode."""

    #: Digest of all sectors data, including
    #: unused sectors.
    ALL = 0
    #: Digest of all files data and attributes and all disk
    #: attributes. The digest includes used parts of catalog
    #: sectors and used parts of sectors occupied by files.
    USED = 1
    #: Digest of files data including load and execution addresses,
    #: but not access mode.
    #: When applied to floppy disk side, generate digest of all files sorted
    #: alphabetically.
    FILE = 2
    #: Digest of file data not including load and execution addresses
    #: or access mode.
    #: When applied to floppy disk side, load and execution addresses are
    #: still included as per ``FILE`` mode.
    DATA = 3


class SizeOption(Enum):
    """Image file size option."""

    #: Keep size, possibly expanding as needed.
    KEEP = 0
    #: Expand to maximum size.
    EXPAND = 1
    #: Shrink to minimum size to include last used sector.
    SHRINK = 2


class OpenMode(Enum):
    """File open mode."""

    #: Create new or open existing file
    ALWAYS = 0
    #: Create new file, fail if the file already exists
    NEW = 1
    #: Open existing file, fail if the file doesn't exist.
    EXISTING = 2


class WarnMode(Enum):
    """Warning mode for validation."""

    #: Display warning for first non-fatal validation error
    FIRST = 0
    #: Don't display validation errors
    NONE = 1
    #: Display all validation errors
    ALL = 2


class InfMode(Enum):
    """Inf files processing mode."""

    #: Write inf files if load or exec address is non-zero,
    #: or host file name is different from dfs name.
    #: Read inf files if present.
    AUTO = 0
    #: Always write inf files. Require inf files on read.
    ALWAYS = 1
    #: Never write inf files.
    #: On read treat all files as data files, don't look for extra inf files.
    NEVER = 2


class TranslationMode(Enum):
    """Mode for translating dfs filename to host filename characters."""

    #: Replaces characters illegal on Windows with underscore
    STANDARD = 0
    #: Replaces all characters, other than digits and letters, with underscore
    SAFE = 1
