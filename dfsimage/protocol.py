# pylint: disable = missing-module-docstring
# pylint: disable = missing-class-docstring
# pylint: disable = missing-function-docstring
# pylint: disable = invalid-name
# pylint: disable = multiple-statements

from typing import Protocol, Callable, TypeVar, Tuple, Optional
from typing import Union, List, Dict
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

    def parse_name(self, name: str, is_pattern: bool) -> Tuple[
        str, Optional[str], Optional[int]]: ...

    def parse_pattern(self, name: str) -> ParsedPattern: ...

    @overload
    def compile_pattern(self, pattern: None) -> None: ...

    @overload
    def compile_pattern(self, pattern: Union[
        str, List[str], ParsedPattern, PatternList]) -> PatternList: ...

    def compile_pattern(self, pattern: PatternUnion) -> Optional[PatternList]: ...

    def to_fullname(self, filename: str,
                    head: int = None) -> Tuple[str, Optional[int]]: ...

    def _sector(self, head: int, track: int, sector: int) -> memoryview: ...

    def _logical_sector(self, head: int, sector: int) -> memoryview: ...

    def _track(self, head: int, track: int) -> memoryview: ...

    def get_sectors(self, head: int, start_track: int, start_sector: int,
                    end_track: int, end_sector: int, used_size: int = None) -> Sectors: ...

    def get_logical_sectors(self, head: int, start_logical_sector: int,
                            end_logical_sector: int, used_size: int = None) -> Sectors: ...

    def add_file(self, filename: str, data: bytes, load_addr: int = None,
                 exec_addr: int = None, locked=False, replace=False,
                 ignore_access=False, no_compact=False,
                 default_head: int = None): ...

    def delete(self, filename: str, ignore_access=False, silent=False,
               default_head: int = None) -> bool: ...

    def rename(self, from_name: str, to_name: str, replace=False,
               ignore_access=False, no_compact=False, silent=False,
               default_head: int = None) -> bool: ...

    def copy(self, from_name: str, to_name: str, replace=False,
             ignore_access=False, no_compact=False,
             preserve_attr=False, silent=False,
             default_head: int = None) -> bool: ...

    def destroy(self, pattern: PatternUnion, ignore_access=False,
                silent=False, default_head: int = None) -> int: ...

    def lock(self, pattern: PatternUnion, silent=False,
             default_head: int = None) -> int: ...

    def unlock(self, pattern: PatternUnion, silent=False,
               default_head: int = None) -> int: ...

    def import_files(self, os_files: Union[str, List[str]],
                     dfs_names: Union[str, List[str]] = None,
                     inf_mode: int = None,
                     load_addr: int = None, exec_addr: int = None,
                     locked: bool = None,
                     replace=False, ignore_access=False,
                     no_compact=False, continue_on_error=False,
                     verbose=False, silent=False,
                     default_head: int = None) -> int: ...

    def export_files(self, output: str,
                     files: PatternUnion = None,
                     create_directories=False,
                     translation: Union[int, bytes] = None,
                     inf_mode: int = None, include_drive=False,
                     replace=False, continue_on_error=False,
                     verbose=False, silent=False,
                     default_head: int = None) -> int: ...

    def backup(self, source, warn_mode: int = None, default_head: int = None): ...

    def copy_over(self, source, pattern: PatternUnion,
                  replace=False, ignore_access=False, no_compact=False,
                  change_dir=False, preserve_attr=False,
                  continue_on_error=False, verbose=False, silent=False,
                  default_head: int = None) -> int: ...


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

    def to_fullname(self, name: str) -> str: ...

    def _sector(self, track: int, sector: int) -> memoryview: ...

    def _logical_sector(self, sector: int) -> memoryview: ...

    def _track(self, track: int) -> memoryview: ...

    def get_sectors(self, start_track: int, start_sector: int,
                    end_track: int, end_sector: int, used_size: int = None) -> Sectors: ...

    def get_logical_sectors(self, start_logical_sector: int,
                            end_logical_sector: int, used_size: int = None) -> Sectors: ...

    def get_all_sectors(self) -> Sectors: ...

    def check_sectors_allocation(self, warnall: bool = False) -> bool: ...

    def check_valid(self) -> None: ...

    def get_entry(self, index: Union[int, str]): ...
