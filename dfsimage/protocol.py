# pylint: disable = missing-module-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = missing-function-docstring
# pylint: disable = invalid-name
# pylint: disable = multiple-statements

from typing import Protocol, Callable, TypeVar, Tuple, Optional
from typing import Union, Dict
from typing import overload

from .mmbentry import MMBEntry
from .sectors import Sectors

from .pattern import ParsedPattern, PatternList, PatternUnion

C_co = TypeVar('C_co', covariant=True)  # pylint: disable = invalid-name
T = TypeVar('T')  # pylint: disable = invalid-name


class Property(Protocol[C_co, T]):
    fget: Callable[[C_co], T]


class EntryProtocol(Protocol):
    pass


class ImageProtocol(Protocol):
    path: str
    filename: str
    basename: str
    modified: bool
    heads: int
    sectors_per_head: int
    tracks: int
    isvalid: bool
    mod_seq: int
    current_dir: str
    default_side: int
    locked: bool
    initialized: bool
    _mmb_entry: Optional[MMBEntry]
    MMB_STATUS_MAP: Dict[int, str]

    @property
    def index(self) -> int: ...

    @property
    def is_mmb(self) -> bool: ...

    @property
    def _mmb_status_byte(self) -> int: ...

    @property
    def displayname(self) -> str: ...

    def _parse_name(self, name: str, is_pattern: bool) -> Tuple[
        str, Optional[str], Optional[int]]: ...

    def _parse_pattern(self, name: str) -> ParsedPattern: ...

    @overload
    def _compile_pattern(self, pattern: None) -> None: ...

    @overload
    def _compile_pattern(self, pattern: PatternUnion) -> PatternList: ...

    def _compile_pattern(self, pattern: Optional[PatternUnion]) -> Optional[PatternList]: ...

    def _to_fullname(self, filename: str,
                     head: int = None) -> Tuple[str, Optional[int]]: ...

    def _sector(self, head: int, track: int, sector: int) -> memoryview: ...

    def _logical_sector(self, head: int, sector: int) -> memoryview: ...

    def _track(self, head: int, track: int) -> memoryview: ...

    def get_sectors(self, head: int, start_track: int, start_sector: int,
                    end_track: int, end_sector: int, used_size: int = None) -> Sectors: ...

    def get_logical_sectors(self, head: int, start_logical_sector: int,
                            end_logical_sector: int, used_size: int = None) -> Sectors: ...


class SideProtocol(Protocol):
    image: ImageProtocol
    modified: bool
    head: int
    total_sectors: int
    number_of_files: int
    number_of_sectors: int
    isvalid: bool

    @property
    def image_displayname(self) -> str: ...

    @property
    def sha1(self) -> str: ...

    @property
    def sha1files(self) -> str: ...

    @property
    def sha1used(self) -> str: ...

    @property
    def free_sectors(self) -> int: ...

    @property
    def used_sectors(self) -> int: ...

    @property
    def largest_free_block(self) -> int: ...

    @property
    def last_used_sector(self) -> int: ...

    def _to_fullname(self, name: str) -> str: ...

    def _sector(self, track: int, sector: int) -> memoryview: ...

    def _logical_sector(self, sector: int) -> memoryview: ...

    def _track(self, track: int) -> memoryview: ...

    def get_sectors(self, start_track: int, start_sector: int,
                    end_track: int, end_sector: int, used_size: int = None) -> Sectors: ...

    def get_logical_sectors(self, start_logical_sector: int,
                            end_logical_sector: int, used_size: int = None) -> Sectors: ...

    def get_all_sectors(self) -> Sectors: ...

    def _check_sectors_allocation(self, warnall: bool = False) -> bool: ...

    def _check_valid(self) -> None: ...

    def get_entry(self, index: Union[int, str]): ...
