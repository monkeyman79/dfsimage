"""Common constants for the package."""

LIST_FORMAT_RAW = 0
LIST_FORMAT_INFO = 1
LIST_FORMAT_INF = 2
LIST_FORMAT_CAT = 3
LIST_FORMAT_JSON = 4
LIST_FORMAT_XML = 5
LIST_FORMAT_TABLE = 6
LIST_FORMAT_DCAT = 7

DIGEST_MODE_ALL = 0
DIGEST_MODE_USED = 1
DIGEST_MODE_FILE = 2
DIGEST_MODE_DATA = 3

SIZE_OPTION_KEEP = 0
SIZE_OPTION_EXPAND = 1
SIZE_OPTION_SHRINK = 2

OPEN_MODE_ALWAYS = 0
OPEN_MODE_NEW = 1
OPEN_MODE_EXISTING = 2

WARN_FIRST = 0
WARN_NONE = 1
WARN_ALL = 2

INF_MODE_AUTO = 0
INF_MODE_ALWAYS = 1
INF_MODE_NEVER = 2

TRANSLATION_STANDARD = 0
TRANSLATION_SAFE = 1

CATALOG_SECTORS = 2
CATALOG_SECTOR1 = 0
CATALOG_SECTOR2 = 1
SECTORS = 10
SECTOR_SIZE = 256
TRACK_SIZE = SECTORS * SECTOR_SIZE
DOUBLE_TRACKS = 80
SINGLE_TRACKS = 40
DOUBLE_SECTORS = DOUBLE_TRACKS * SECTORS
SINGLE_SECTORS = SINGLE_TRACKS * SECTORS
MAX_FILES = 31

MMB_MAX_ENTRIES = 511
MMB_INDEX_ENTRY_SIZE = 16
MMB_INDEX_SIZE = (MMB_MAX_ENTRIES + 1) * MMB_INDEX_ENTRY_SIZE
MMB_DISK_SIZE = TRACK_SIZE * DOUBLE_TRACKS
MMB_SIZE = MMB_INDEX_SIZE + MMB_MAX_ENTRIES * MMB_DISK_SIZE

MMB_STATUS_OFFSET = 15

MMB_STATUS_LOCKED = 0
MMB_STATUS_UNLOCKED = 15
MMB_STATUS_UNINITIALIZED = 240

MMB_STATUS_UNINITIALIZED_MASK = 240
