"""Manages DFS floppy disk image loaded (or mapped) into memory."""

import os
import sys
import hashlib
import itertools

from io import SEEK_SET

from typing import List, Union, Optional
from typing import Iterator, Tuple, Dict, Set, IO
from typing import cast, overload

from . import simplewarn
from .simplewarn import warn

from .consts import SECTORS, SECTOR_SIZE, TRACK_SIZE
from .consts import SINGLE_TRACKS, DOUBLE_TRACKS, CATALOG_SECTORS
from .consts import SIZE_OPTION_KEEP, SIZE_OPTION_EXPAND, SIZE_OPTION_SHRINK
from .consts import LIST_FORMAT_CAT, LIST_FORMAT_INF, LIST_FORMAT_INFO
from .consts import LIST_FORMAT_RAW
from .consts import LIST_FORMAT_JSON, LIST_FORMAT_XML, LIST_FORMAT_TABLE
from .consts import OPEN_MODE_ALWAYS, OPEN_MODE_EXISTING, OPEN_MODE_NEW
from .consts import WARN_FIRST
from .consts import INF_MODE_ALWAYS, INF_MODE_AUTO, INF_MODE_NEVER
from .consts import TRANSLATION_STANDARD, TRANSLATION_SAFE

from .misc import bchr, LazyString, json_dumps, xml_dumps
from .misc import DFSWarning

from .conv import unicode_to_bbc, NAME_SAFE_TRANS, NAME_STD_TRANS

from .protocol import Property, ImageProtocol
from .sectors import Sectors
from .entry import Entry
from .side import Side
from .inf import Inf, InfCache, canonpath


class Image:
    """DFS floppy disk image loaded (or mapped) into memory."""

    TABLE_FORMAT = (
        "{image_filename:12}|"
        "{number_of_sides}|{tracks}|{size:6}|{min_size:6}|{max_size:6}|"
        "{is_valid:1}|{sha1}"
        )

    def __init__(self, fname: str, heads: int, tracks: int, linear: bool = None) -> None:
        """Construct new 'Image' object with allocated bytearray for sectors data.

        Args:
            heads: Number of floppy sides - 1 or 2.
            tracks: Number of tracks per side - 80 or 40. Default is 80.
            linear: Optional; This flags is always True for single sided disks.
                For double sided disks, it indicates, that data for each side is
                stored continuously as opposed to default layout where track data
                for each side are interleaved.
        """
        if heads not in (1, 2):
            raise ValueError("invalid number of disc sides")

        if tracks not in (SINGLE_TRACKS, DOUBLE_TRACKS):
            raise ValueError("invalid number of tracks per side")

        self._modified = False
        if heads == 1:
            self.linear = True
        elif linear is None:
            self.linear = False
        else:
            self.linear = linear
        self.heads = heads
        self.tracks = tracks
        self.sectors_per_head = self.tracks * SECTORS
        self._data = bytearray(bchr(0xE5) * (self.heads * self.tracks * TRACK_SIZE))
        self.dataview = memoryview(self._data)
        self.path = os.path.abspath(fname)
        self.filename = os.path.basename(fname)
        self.basename, _ = os.path.splitext(self.filename)
        self.original_size = 0
        self.sides = tuple(Side(self, head) for head in range(0, self.heads))
        self.isvalid = False  # Until validated
        self.mod_seq = 0
        self.file: Optional[IO[bytes]] = None
        self.is_read_only = True
        self.is_new_image = False
        self._current_dir = '$'
        self._default_head: Optional[int] = None if self.heads != 1 else 0

    def _not_closed(self):
        if self._data is None:
            raise ValueError('image file closed')

    @property
    def current_dir(self) -> str:
        """Current directory name.

        Used for listing and as a default for file names without directory.
        This is property of the Image object, not present in the floppy image.

        Raises:
            ValueError: Assigned value length is other than 1 or invalid character.
        """
        return self._current_dir

    @current_dir.setter
    def current_dir(self, value) -> None:
        if value is None:
            value = '$'
        if len(value) != 1 or not Entry.isnamechar(unicode_to_bbc(value)
                                                   .encode('ascii')[0]):
            raise ValueError("invalid directory name")
        self._current_dir = value

    @property
    def default_side(self) -> Optional[int]:
        """Default disk side.

        Value is 1 - based (i.e. 1 is first side, 2 is second side).

        Default disk side for listing or file operations.
        If default_side is None, listing will be generated for both sides,
        new files will be created where there is enough space,
        single file operations will fail if there is ambiguity, and
        multiple file operations will affect files on both sides.

        Disk side can be overridden for file operation by prefixing
        file name or pattern with drive number as in DFS: ":0.filename" for
        first side, ":2.filename" for second side.
        """
        if self._default_head is None:
            return None
        return self._default_head + 1

    @default_side.setter
    def default_side(self, value: Optional[int]) -> None:
        if value is not None:
            if not 0 < value <= self.heads:
                raise ValueError("invalid disk side number")
            self._default_head = value - 1
        elif self.heads != 1:
            self._default_head = None

# pylint: disable=missing-function-docstring, no-self-use

    @overload
    def get_side(self, head: None) -> Optional[Side]:
        ...

    @overload
    def get_side(self, head: int) -> Side:
        ...

# pylint: enable=missing-function-docstring, no-self-use

    def get_side(self, head: Optional[int] = None) -> Optional[Side]:
        """Get 'Side' object representing single side of a disk.

        Args:
            head: Floppy side - 0 or 1. If this parameter is None,
                get default side or None.
        Returns:
            A 'Side' object.
        """
        self._not_closed()
        if head is None:
            head = self._default_head
            if head is None:
                return None
        return self.sides[head]

    @property
    def default_sides(self) -> Tuple:
        """Get tuple object containing default side or all sides if default side is None."""
        head = self._default_head
        if head is None:
            return tuple(self.sides)
        return (self.get_side(head),)

    @property
    def modified(self) -> bool:
        """Image data has been changed since it was loaded or saved."""
        return self._modified

    @modified.setter
    def modified(self, value: bool) -> None:
        if value:
            if self.is_read_only:
                raise PermissionError("image open for read only")
            self.mod_seq += 1
        self._modified = value

    def track_start(self, head: int, track: int) -> int:
        """Get offset to start of track data.

        Args:
            head: Floppy side - 0 or 1.
            track: Track number on floppy side - 0 to 79.
        Returns:
            Offset to start of track data.
        """
        if self.linear:
            return (head * self.tracks + track) * TRACK_SIZE
        return (track * self.heads + head) * TRACK_SIZE

    def track_end(self, head: int, track: int) -> int:
        """Get offset to end of track data.

        Args:
            head: Floppy side - 0 or 1.
            track: Track number on floppy side - 0 to 79.
        Returns:
            Offset to end of track data (first byte after).
        """
        return self.track_start(head, track) + TRACK_SIZE

    def sector_start(self, head: int, track: int, sector: int) -> int:
        """Get offset to start of sector data.

        Args:
            head: Floppy side - 0 or 1.
            track: Track number on floppy side - 0 to 79.
            sector: Sector number on track - 0 to 9.
        Returns:
            Offset to start of sector data.
        """
        return self.track_start(head, track) + sector * SECTOR_SIZE

    def sector_end(self, head: int, track: int, sector: int) -> int:
        """Get offset to end of sector data.

        Args:
            head: Floppy side - 0 or 1.
            track: Track number on floppy side - 0 to 79.
            sector: Sector number on track - 0 to 9.
        Returns:
            Offset to end of sector data (first byte after).
        """
        return self.sector_start(head, track, sector) + SECTOR_SIZE

    def logical_sector_start(self, head: int, logical_sector: int) -> int:
        """Get offset to start of sector data by logical sector number.

        Args:
            head: Floppy side - 0 or 1.
            sector: Logical sector number on the side - 0 to 799.
        Returns:
            Offset to start of sector data.
        """
        track, sector = Image.logical_to_physical(logical_sector)
        return self.sector_start(head, track, sector)

    def logical_sector_end(self, head: int, logical_sector: int) -> int:
        """Get offset to end of sector data by logical sector number.

        Args:
            head: Floppy side - 0 or 1.
            sector: Logical sector number on the side - 0 to 799.
        Returns:
            Offset to end of sector data (first byte after).
        """
        track, sector = Image.logical_to_physical(logical_sector)
        return self.sector_start(head, track, sector) + SECTOR_SIZE

    def _sector(self, head: int, track: int, sector: int) -> memoryview:
        """Get 'memoryview' object to sector data.

        Warning: If you write data directly to underlying sectors, set 'modified'
        property of the Image object to True, to ensure that cached data gets
        synced with real contents and that image will be written back to disk by
        'save' or 'close' method. If you write to catalog sectors, call 'validate'
        before using high level file access.

        Args:
            head: Floppy side - 0 or 1.
            track: Track number on floppy side - 0 to 79.
            sector: Sector number on track - 0 to 9.
        Returns:
            A 'memoryview' to sector data.
        Raises:
            IndexError: Invalid head, track or sector number
        """
        self._not_closed()
        if head < 0 or head >= self.heads:
            raise IndexError("invalid head number")
        if track < 0 or track >= self.tracks:
            raise IndexError("invalid track number")
        if sector < 0 or sector >= SECTORS:
            raise IndexError("invalid sector number")
        return self.dataview[self.sector_start(head, track, sector):
                             self.sector_end(head, track, sector)]

    def _logical_sector(self, head: int, logical_sector: int) -> memoryview:
        """Get 'memoryview' object to sector data by logical sector number.

        Warning: If you write data directly to underlying sectors, set 'modified'
        property of the Image object to True, to ensure that cached data gets
        synced with real contents and that image will be written back to disk by
        'save' or 'close' method. If you write to catalog sectors, call
        'validate' before using high level file access.

        Args:
            head: Floppy side - 0 or 1.
            logical_sector: Logical sector number on the side - 0 to 799.
        Returns:
            A 'memoryview' to sector data.
        Raises:
            IndexError: Invalid head or sector number
        """
        track, sector = Image.logical_to_physical(logical_sector)
        return self._sector(head, track, sector)

    def _track(self, head: int, track: int) -> memoryview:
        """Get 'memoryview' object to entire track data.

        Warning: If you write data directly to underlying sectors, set 'modified'
        property of the Image object to True, to ensure that cached data gets
        synced with real contents and that image will be written back to disk by
        'save' or 'close' methods. If you write to catalog sectors, call
        'validate' before using high level file access.

        Args:
            head: Floppy side - 0 or 1.
            track: Track number on side - 0 to 79.
        Returns:
            A 'memoryview' to track data.
        Raises:
            IndexError: Invalid head or track number
        """
        self._not_closed()
        if head < 0 or head >= self.heads:
            raise IndexError("invalid head number")
        if track < 0 or track >= self.tracks:
            raise IndexError("invalid track number")
        track_start = self.track_start(head, track)
        track_end = self.track_end(head, track)
        return self.dataview[track_start:track_end]

    def _validate_sectors(self, head: int, start_track: int, start_sector: int,
                          end_track: int, end_sector: int):
        self._not_closed()
        if head < 0 or head >= self.heads:
            raise IndexError("invalid head number")
        if start_track < 0 or start_track >= self.tracks:
            raise IndexError("invalid track number")
        if end_track < 0 or end_track > self.tracks:
            raise IndexError("invalid track number")
        if start_sector < 0 or start_sector >= SECTORS:
            raise IndexError("invalid sector number")
        if end_sector < 0 or end_sector > SECTORS or (end_track == self.tracks
                                                      and end_sector != 0):
            raise IndexError("invalid sector number")
        if start_track > end_track or (start_track == end_track
                                       and start_sector > end_sector):
            raise ValueError("start sector after end sector")

    def get_sectors(self, head: int, start_track: int, start_sector: int,
                    end_track: int, end_sector: int,
                    used_size: int = None) -> Sectors:
        """Get 'Sectors' object for sectors range.

        Return 'Sectors' object referencing possibly non-continuous area in
        image data corresponding to sequence of sectors. The area covers sectors
        in range from the start sector to the end sector exclusively, i.e.
        end_track and end_sector should point to first sector after the range.
        For end_track and end_sector, value pairs (80, 0) and (79, 10)
        (or (40, 0) and (39, 10) for 40 track disks) are both valid and point to
        the same end-of-disk-side sector.

        Args:
            head: Floppy side - 0 or 1.
            start_track: Start track number - 0 to 79.
            start_sector: Start sector number on track - 0 to 9.
            end_track: End track number - 0 to 80.
            end_sector: End sector number on track - 0 to 10.
            used_size: Size in bytes of data contained in sectors sequence
                especially last sector can be only partially utilized.
        Raises:
            IndexError: Invalid head, track or sector number
            ValueError: Start sector is after end sector.
        """
        self._validate_sectors(head, start_track, start_sector,
                               end_track, end_sector)
        chunks = []
        count = 0
        if self.linear:
            count += (end_track - start_track) * SECTORS + end_sector - start_sector
            start = self.sector_start(head, start_track, start_sector)
            end = self.sector_start(head, end_track, end_sector)
            if start != end:
                chunks.append(self.dataview[start:end])

        else:
            # Go though all tracks but last and append data chunks
            while start_track != end_track:
                start = self.sector_start(head, start_track, start_sector)
                end = self.sector_start(head, start_track, SECTORS)
                dataview = self.dataview[start:end]
                if len(dataview) != 0:
                    chunks.append(dataview)
                count += SECTORS - start_sector
                start_sector = 0
                start_track += 1
            # Append last data chunk
            if start_sector != end_sector:
                start = self.sector_start(head, start_track, start_sector)
                end = self.sector_start(head, start_track, end_sector)
                dataview = self.dataview[start:end]
                if len(dataview) != 0:
                    chunks.append(dataview)
                count += end_sector - start_sector
                start_sector = end_sector

        return Sectors(self, chunks, count * SECTOR_SIZE, used_size)

    def get_logical_sectors(self, head: int, start_logical_sector: int,
                            end_logical_sector: int, used_size: int = None) -> Sectors:
        """Get 'Sectors' object for sectors range by logical sector numbers.

        Args:
            head: Floppy side - 0 or 1.
            start_logical_sector: Start sector logical number on track - 0 to 799.
            end_logical_sector: End sector number on track - 0 to 800.
            used_size: Size in bytes of data contained in sectors sequence
                especially last sector can be only partially utilized.
        Raises:
            IndexError: Invalid sector number
            ValueError: Start sector is after end sector.
        """
        start_track, start_sector = Image.logical_to_physical(start_logical_sector)
        end_track, end_sector = Image.logical_to_physical(end_logical_sector)
        return self.get_sectors(head, start_track, start_sector,
                                end_track, end_sector, used_size)

    @property
    def min_size(self) -> int:
        """Minimal disk image size.

        Size of disk image when only used sectors are present in the image file.
        """
        self._not_closed()
        end = 0
        for head in range(0, self.heads):
            last_used = self.get_side(head).last_used_sector - 1
            end = max(end,
                      self.logical_sector_end(head, last_used))
        return end

    @property
    def max_size(self) -> int:
        """Maximal disk image size.

        Size of disk image when all sectors are present in the image file.
        """
        self._not_closed()
        return self.sector_end(self.heads - 1, self.tracks - 1, SECTORS - 1)

    def __get_size_for_save(self, size_option: int = None) -> int:
        if size_option is None:
            size_option = SIZE_OPTION_KEEP
        if (size_option == SIZE_OPTION_EXPAND
                or self.is_new_image and size_option == SIZE_OPTION_KEEP):
            return self.max_size
        if (size_option == SIZE_OPTION_SHRINK or
                self.modified and self.original_size < self.min_size):
            return self.min_size
        return self.original_size

    def get_entry(self, index: Union[int, str]) -> 'Entry':
        """Get file entry by index or name.

        Args:
            index: File entry index in range 0 - 30, or file name
        Raises:
            ValueError: Index is out of valid range.
        Returns:
            New 'Entry' object.
        """
        if isinstance(index, int):
            sides = self.default_sides
            if index < 0:
                raise IndexError("invalid file entry index")
            for side in sides:
                if index < side.number_of_files:
                    return side.get_entry(index)
                index -= side.number_of_files
            raise IndexError("invalid file entry index")

        if isinstance(index, str):
            entry = self.find_entry(index)
            if entry is None:
                raise KeyError("file not found")
            return entry

        raise TypeError("index must be str or int, not %s" % type(index).__name__)

    def __iter__(self) -> Iterator[Entry]:
        """Iterate over all files in default sides."""
        return itertools.chain.from_iterable(self.default_sides)

    def __getitem__(self, index: Union[int, str]) -> Entry:
        return self.get_entry(index)

    def __len__(self) -> int:
        return sum(side.number_of_files for side in self.default_sides)

    def __str__(self) -> str:
        """Get string representation of Image."""
        if self.file is None:
            return "<Image %s %dS %dT closed>" % (self.filename, self.heads,
                                                  self.tracks)
        return "<Image %s %dS %dT %s>" % (self.filename, self.heads, self.tracks,
                                          self.sha1)

    def __repr__(self) -> str:
        """Textual representation."""
        return self.__str__()

    def hexdump(self, start: int = None, size: int = None, width: int = None,
                ellipsis: bool = None, file=sys.stdout) -> None:
        """Hexdecimal dump of disk image.

        Args:
            start: Optional; Starting offset.
            size: Optional; Number of bytes to dump.
            width: Optional; Number of bytes per line.
            ellipsis: Optional; If ellipsis is True, repeating lines will be skipped.
            file: Output stream. Default is sys.stdout.
        """
        Sectors.hexdump_buffer(self._data, start, size, width, ellipsis,
                               file=file)

    @staticmethod
    def logical_to_physical(sector: int) -> Tuple[int, int]:
        """Convert logical sector number to physical track and sector number.

        Args:
            sector: Logical sector number.
        Returns:
            Tuple consisting of physical track and sector numbers.
        """
        return sector // SECTORS, sector % SECTORS

    @staticmethod
    def physical_to_logical(track: int, sector: int) -> int:
        """Convert physical track and sector number to logical sector number.

        This method doesn't validate track number. It will be validated when
        logical sector number is used.

        Args:
            track: Physical track number.
            sector: Physical sector number.
        Returns:
            Logical sector numbers.
        Raises:
            IndexError: Sector number is outside of valid range 0 - 10.
                Value 10 is valid as pointing to a sector after last sector on
                a track.
        """
        if sector > SECTORS:
            raise IndexError("invalid sector number")
        return track * SECTORS + sector

    @staticmethod
    def sides_and_tracks_str(heads: int, tracks: int) -> str:
        """Format string describing disk physical properties for error messages."""
        return "%d side%s %d tracks" % (heads,
                                        "" if heads == 1 else "s", tracks)

    def validate(self, warn_mode: int = WARN_FIRST) -> bool:
        """Validate disk image.

        Validate disk image. Raise exception if a fatal error is encountered.
        If a non-fatal error is encountered, issue a warning and mark disk side
        as invalid, preventing disk modifications.

        Returns:
            Validation results - True if disk is valid, False otherwise.
        """
        self._not_closed()
        isvalid = True

        # Validate both sides
        for side in self.sides:
            isvalid &= side.validate(warn_mode)

        self.isvalid = isvalid

        return isvalid

    def _get_heads_from_pattern(self, pattern: Union[str, List[str]] = None):
        # List default sides, or sides mentioned in pattern(s)
        if pattern is None:
            pattern = []
        elif isinstance(pattern, str):
            pattern = [pattern]

        # Get drive names from pattern
        heads: Set[Optional[int]] = set((self.parse_name(pat, True)[2]
                                         for pat in pattern))
        # If pattern list is empty or contains pattern without drive name, add
        # default side(s)
        if len(heads) == 0 or None in heads:
            heads.discard(None)
            if self._default_head is not None:
                heads.add(self._default_head)
            else:
                heads.update(set(range(0, self.heads)))
        head_list = list(heads)
        head_list.sort()
        return head_list

    PROPERTY_NAMES = {
        "image_path": "Full path of the floppy disk image file.",
        "image_filename": "File name of the floppy disk image file.",
        "image_basename": "File name of the floppy disk image file without "
                          "extension.",
        "number_of_sides": "Number of floppy disk image sides.",
        "tracks": "Number of tracks on each side.",
        "size": "Current disk image size.",
        "min_size": "Minimum disk image size to include last used sector.",
        'max_size': "Maximum disk image size.",
        "is_valid": "True if disk validation succeeded.",
        "is_linear": "True if floppy disk image file has linear layout "
                     "is single sided or is double sided ssd file.",
        "sha1": "SHA1 digest of the entire disk image file."
    }

    def get_properties(self, for_format: bool, recurse: bool,
                       level: int = 0,
                       pattern: Union[str, List[str]] = None,
                       sort: bool = False) -> Union[List, Dict[str, object]]:
        """Get dictionary of all disk image properties.

        Args:
            for_format: If True, include additional redundant properties
                suitable for custom listing format, but not needed
                for dump.
            recurse: If True, include list of sides and recursively list
                of files with their properties in returned map.
            level: Optional; If level is -1 skip disk image properties and
                instead return list of sides with their properties. If level
                is -2, return list of files.
        Returns:
            Dictionary of disk image properties.
        """
        self._not_closed()

        if level >= 0:
            attrs = {
                'image_path': self.path,
                'image_filename': self.filename,
                'number_of_sides': self.heads,
                'tracks': self.tracks,
                'size': self.__get_size_for_save(SIZE_OPTION_KEEP),
                'min_size': self.min_size,
                "max_size": self.max_size,
                "is_valid": self.isvalid,
                "is_linear": self.linear,
                "sha1": LazyString(cast(Property['Image', str],  # pylint: disable=no-member
                                        Image.sha1).fget, self)
                }
            if not for_format:
                attrs["sha1"] = str(attrs["sha1"])
            if for_format:
                attrs["image_basename"] = self.basename

        if recurse or level < 0:
            heads = self._get_heads_from_pattern(pattern)
            side_list = [self.get_side(head)
                         .get_properties(for_format=False, recurse=recurse,
                                         level=level+1, pattern=pattern,
                                         sort=sort)
                         for head in heads]

            if level == -2:
                return [file for file_list in side_list for file in file_list]

            if level < 0:
                return side_list

            attrs["sides"] = side_list

        return attrs

    def listing_header(self, fmt: Union[int, str] = None,
                       file=sys.stdout) -> None:
        """Print listing header line common for entire floppy image file.

        See Image.PROPERTY_NAMES for list of available keys.

        Args:
            fmt: Selected format. The header is generated with str.format
                function. Nothing is printed if this parameter is one on
                LIST_FORMAT_.... constants other than LIST_FORMAT_TABLE.
            file: Output stream. Default is sys.stdout.
        Raises:
            ValueError: Parameter 'fmt' is invalid.
        """
        self._not_closed()
        if fmt is None or fmt == '':
            return
        if fmt == LIST_FORMAT_TABLE:
            fmt = Image.TABLE_FORMAT
        if isinstance(fmt, str):
            attrs = self.get_properties(for_format=True, recurse=False)
            print(fmt.format_map(cast(Dict[str, object], attrs)), file=file)
        elif fmt not in (LIST_FORMAT_RAW, LIST_FORMAT_INFO,
                         LIST_FORMAT_INF, LIST_FORMAT_CAT,
                         LIST_FORMAT_JSON, LIST_FORMAT_XML):
            raise ValueError("invalid listing format")

    def listing(self, fmt: Union[int, str] = None,
                pattern: Union[str, List[str]] = None,
                side_header_fmt: Union[int, str] = None,
                side_footer_fmt: Union[int, str] = None,
                img_header_fmt: Union[int, str] = None,
                img_footer_fmt: Union[int, str] = None,
                sort: bool = None, file=sys.stdout) -> None:
        """Print file listing for all (single or both) disk sides.

        Print catalog listing using predefined format or custom
        formatting strings.

        Predefined formats are:
            LIST_FORMAT_RAW (0)   - Lists file names, no header.
            LIST_FORMAT_INFO (1)  - As displayed by *INFO command.
            LIST_FORMAT_INF (2)   - As in .inf files.
            LIST_FORMAT_CAT (3)   - As displayed by *CAT command.
            LIST_FORMAT_JSON (4)  - Generate JSON
            LIST_FORMAT_XML (5)   - Generate XML
            LIST_FORMAT_TABLE (6) - Fixed-width text table.

        For list of keys available for custom image header formatting string see
        Image.PROPERTY_NAMES.

        For list of keys available for custom side header formatting string see
        Side.PROPERTY_NAMES.

        For list of keys available for custom file entry formatting string see
        Entry.PROPERTY_NAMES.

        Args:
            fmt: Optional; Selected file entry format. Value can be one of
                LIST_FORMAT_... constants or custom formatting string.
            pattern: Optional; List only files matching pattern (see Entry.match).
            side_header_fmt: Optional; Selected side listing header format.
                Value can be one of LIST_FORMAT_... constants or
                custom formatting string. Default is `fmt` if it is one for
                predefined formats, otherwise no header.
            side_footer_fmt: Optional; Formatting string for side listing footer.
                Default is no side listing footer.
            img_header_fmt: Optional; Formatting string for image listing header.
                Default ia no image header.
            img_footer_fmt: Optional; Formatting string for image listing footer.
                Default is no image footer.
            sort: Optional; If this flag is True, displayed files are sorted
                alphabetically. It is enabled by default for LIST_FORMAT_CAT format
                and disabled for all other formats.
            file: Output stream. Default is sys.stdout.
        Raises:
            ValueError: Parameter 'fmt' or 'header_fmt' is invalid.
        """
        self._not_closed()
        if img_header_fmt is None and not isinstance(fmt, str):
            img_header_fmt = fmt
        if img_header_fmt is not None and img_header_fmt != '':
            self.listing_header(img_header_fmt, file=file)

        if fmt == LIST_FORMAT_JSON:
            attrs = self.get_properties(for_format=False, recurse=True,
                                        pattern=pattern)
            print(json_dumps(attrs), file=file)
        elif fmt == LIST_FORMAT_XML:
            attrs = self.get_properties(for_format=False, recurse=True,
                                        pattern=pattern)
            print(xml_dumps(attrs, "image"), file=file)
        else:
            heads = self._get_heads_from_pattern(pattern)
            for head in heads:
                self.get_side(head).listing(fmt, pattern,
                                            header_fmt=side_header_fmt,
                                            footer_fmt=side_footer_fmt,
                                            sort=sort, file=file)

        if img_footer_fmt is not None and img_footer_fmt != '':
            self.listing_header(img_footer_fmt, file=file)

    def cat(self, pattern: str = None, file=sys.stdout) -> None:
        """Generate file listing as produced by *CAT command.

        Args:
            pattern: Optional; Only list files matching pattern (see Entry.match).
            file: Output stream. Default is sys.stdout.
        """
        self.listing(LIST_FORMAT_CAT, pattern, file=file)

    def info(self, pattern: str = None, file=sys.stdout) -> None:
        """Generate file listing as produced by *INFO command.

        Args:
            pattern: Optional; Only list files matching pattern (see Entry.match).
            file: Output stream. Default is sys.stdout.
        """
        self.listing(LIST_FORMAT_INFO, pattern, file=file)

    def get_digest(self, algorithm: str = None) -> str:
        """Generate hexadecimal digest of entire disk image file.

        Args:
            algorithm: Optional; Algorithm to use instead of the default SHA1.
        Returns:
            Hexadecimal digest string.
        """
        self._not_closed()
        if algorithm is None:
            algorithm = 'sha1'
        size = self.__get_size_for_save()
        data = self._data[0:self.original_size]
        return hashlib.new(algorithm, data[:size],
                           usedforsecurity=False).hexdigest()  # type: ignore[call-arg]

    @property
    def sha1(self) -> str:
        """SHA1 digest of the entire disk image file."""
        return self.get_digest()

    @staticmethod
    def _skip_first_letter(pattern: str) -> int:
        # If this is pattern and starts with '[', look for matching ']',
        # skip ']' immediately following opening brace or '!'
        if len(pattern) != 0 and pattern[0] == '[':
            scan = 1 if len(pattern) <= 1 or pattern[1] != '!' else 2

            if len(pattern) > scan and pattern[scan] == ']':
                scan += 1

            scan = pattern.find(']', scan)
            if scan != -1:
                return scan + 1

        return 1

    def _extract_drive(self, name: str) -> Tuple[str, int]:
        if len(name) < 3 or name[2] != '.':
            raise ValueError("invalid drive name")
        if name[1] not in ('0', '2'):
            raise ValueError("bad drive")
        head = (ord(name[1]) - ord('0')) // 2
        if head >= self.heads:
            raise ValueError("bad drive")
        return name[3:], head

    def parse_name(self, name: str,
                   is_pattern: bool) -> Tuple[str, Optional[str], Optional[int]]:
        """Extract drive and directory from pattern or filename.

        Returns:
            Remaining file name, directory name or None and head number or None.
        Raise:
            ValueError: drive name in pattern is invalid or not present.
        """
        dirname = None
        head = None
        done = False

        # Allow just drive name in place of pattern
        if is_pattern and len(name) == 2 and name[0] == ':':
            if name[1] not in ('0', '2'):
                raise ValueError("bad drive")
            head = (ord(name[1]) - ord('0')) // 2
            if head >= self.heads:
                raise ValueError("bad drive")
            return '*', '?', head

        while not done:
            done = True
            # If name begins with ':', extract drive
            if len(name) > 0 and name[0] == ':':
                name, head = self._extract_drive(name)
                done = False

            # If name begins with '.', set directory to space
            elif len(name) > 0 and name[0] == '.':
                dirname = ' '
                name = name[1:]
                done = False

            # Look for directory name
            else:
                if is_pattern:
                    first_letter = self._skip_first_letter(name)
                else:
                    first_letter = 1

                if len(name) > first_letter and name[first_letter] == '.':
                    dirname = name[:first_letter]
                    name = name[first_letter+1:]
                    done = False

        return name, dirname, head

    def to_fullname(self, filename: str,
                    head: int = None) -> Tuple[str, Optional[int]]:
        """Process filename and add directory name if needed.

        Extract drive number and prepend current directory name ($) if not
        present in filename. Filename is not a pattern - characters *?![] are
        not special and are all valid filename characters.
        """

        if head is None:
            head = self._default_head

        # remove trailing spaces
        filename = filename.rstrip()

        # get drive from filename
        filename, f_dir, f_head = self.parse_name(filename, False)

        # get head number or use default
        if f_head is not None:
            head = f_head

        # no directory in filename - use current dir
        if f_dir is None:
            f_dir = self.current_dir

        # validate filename length
        if len(filename) == 0:
            raise ValueError("empty file name is invalid")
        if len(filename) > 7:
            raise ValueError("file name '%s' too long" % filename)

        # Build full name
        filename = "%s.%s" % (f_dir, filename)

        # validate filename characters
        if any(not Entry.isnamechar(c)
               for c in unicode_to_bbc(filename).encode('ascii')):
            raise ValueError("invalid characters in filename '%s'" % filename)

        return filename, head

    def find_entry(self, filename: str, head: int = None) -> Optional['Entry']:
        """Find entry by filename.

        Args:
            filename: File name, not a pattern
        Return:
            Found entry or None.
        """
        self._not_closed()
        name, head = self.to_fullname(filename, head)
        side = self.get_side(head)
        sides = [side] if side is not None else self.sides
        found_entry = None
        for side in sides:
            entry = side.find_entry(name)
            if entry is not None:
                if found_entry is not None:
                    raise ValueError("ambiguous file name '%s'" % filename)
                found_entry = entry
        return found_entry

    def get_files(self, pattern: Union[str, List[str]] = None,
                  default_head: int = None) -> List[Entry]:
        """List of file entries matching pattern."""
        self._not_closed()
        if default_head is None:
            default_head = self._default_head
        if pattern is None:
            return [file for side in self.sides
                    if default_head is None or side.head == default_head
                    for file in side.files]

        parsed: List[Tuple[str, Optional[str], Optional[int]]]
        if isinstance(pattern, str):
            parsed = [self.parse_name(pattern, True)]
        else:
            parsed = list(self.parse_name(pat, True) for pat in pattern)
        return [file for side in self.sides
                for file in side.files
                if file.match_parsed(parsed, default_head)]

    def delete(self, filename: str, ignore_access=False, silent=False,
               default_head: int = None) -> bool:
        """Delete single file from floppy disk image.

        Args:
            filename: File name, not a pattern.
            ignore_access: Optional; Allow deleting locked files. Default is
                False.
            silent: Optional; Don't raise exception if file doesn't exist.
                Default is False.
            default_head: Default disk side.
        Returns:
            True if file was deleted, otherwise False.
        """
        entry = self.find_entry(filename, default_head)
        if entry is None:
            if not silent:
                raise FileNotFoundError("file '%s' not found" % filename)
            return False

        entry.delete(ignore_access)
        return True

    def rename(self, from_name: str, to_name: str, replace=False,
               ignore_access=False, no_compact=False,
               default_head: int = None) -> bool:
        """Rename single file in floppy image.

        Args:
            from_name: Name of file to rename.
            to_name: New name for file.
            replace: Optional; Allow replacing existing files. Default is False.
            ignore_access: Optional; Allow replacing locked files. Default is
                False.
            silent: Optional; Don't raise exception if file doesn't exist.
                Default is False.
            no_compact: Optional; Fail if there is no continuous block big
                enough for the file when moving file between sides.
                If 'no_compact' is not set, try to compact free
                space. Default is False - i.e. try to compact free
                space if needed.
            default_head: Default disk side.
        Returns:
            True if file was renamed, otherwise False.
        """
        from_entry = self.find_entry(from_name, default_head)
        if from_entry is None:
            raise FileNotFoundError("file '%s' not found" % from_name)

        from_entry.side.check_valid()

        if from_entry.locked and not ignore_access:
            raise PermissionError("file '%s' is locked" % from_entry.fullname)

        to_name, to_head = self.to_fullname(to_name, default_head)
        if to_head is None:
            to_head = from_entry.side.head

        # Renaming file
        if to_head == from_entry.side.head:
            to_entry = self.find_entry(to_name, to_head)
            # Check if file with the same name already exists
            if to_entry is not None:
                if (to_entry.side is from_entry.side
                        and to_entry.index == from_entry.index):
                    raise ValueError("'%s' and '%s' are the same"
                                     % (from_name, to_name))
                if not replace:
                    raise FileExistsError("file '%s' already exists"
                                          % to_entry.fullname)
                to_entry.delete(ignore_access)
                if (from_entry.side is to_entry.side
                        and from_entry.index > to_entry.index):
                    from_entry = cast(Entry, from_entry.side.get_entry(from_entry.index - 1))
                to_entry = None
            from_entry.fullname = to_name

        # Moving file to other side
        else:
            data = from_entry.readall()
            self.add_file(to_name, data, from_entry.load_address,
                          from_entry.exec_address, from_entry.locked,
                          replace=replace,
                          ignore_access=ignore_access, no_compact=no_compact,
                          default_head=to_head)
            from_entry.delete(ignore_access)
        return True

    def copy(self, from_name: str, to_name: str, replace=False,
             ignore_access=False, no_compact=False,
             preserve_attr=False,
             default_head: int = None) -> bool:
        """Copy single file in floppy image.

        Args:
            from_name: Source file name.
            to_name: Destination file name.
            replace: Optional; Allow replacing existing files. Default is False.
            ignore_access: Optional; Allow replacing locked files. Default is
                False.
            no_compact: Optional; Fail if there is no continuous block big
                enough for the file. Otherwise try to compact free
                space. Default is False - i.e. try to compact free
                space if needed.
            preserve_attr: Optional; Preserve locked attribute on copied files.
            default_head: Default disk side.
        Returns:
            True if file was copied, otherwise False.
        """
        from_entry = self.find_entry(from_name, default_head)
        if from_entry is None:
            raise FileNotFoundError("file '%s' not found" % from_name)

        from_entry.side.check_valid()

        to_name, to_head = self.to_fullname(to_name, default_head)
        if to_head is None:
            to_head = from_entry.side.head

        if to_head == from_entry.side.head:
            to_entry = self.find_entry(to_name, to_head)
            # Check if file with the same name already exists
            if to_entry is not None:
                if (to_entry.side is from_entry.side
                        and to_entry.index == from_entry.index):
                    raise ValueError("'%s' and '%s' are the same"
                                     % (from_name, to_name))
                if not replace:
                    raise FileExistsError("file '%s' already exists"
                                          % to_entry.fullname)
                to_entry.delete(ignore_access)
                if (from_entry.side is to_entry.side
                        and from_entry.index > to_entry.index):
                    from_entry = cast(Entry, from_entry.side.get_entry(from_entry.index - 1))
                to_entry = None

        locked = preserve_attr and from_entry.locked
        data = from_entry.readall()
        self.add_file(to_name, data, from_entry.load_address,
                      from_entry.exec_address, locked, replace=replace,
                      ignore_access=ignore_access, no_compact=no_compact,
                      default_head=to_head)
        return True

    def destroy(self, pattern: Union[str, List[str]], ignore_access=False,
                default_head: int = None) -> int:
        """Delete all files matching pattern.

        Args:
            pattern: Pattern or list or patterns.
            ignore_access: Optional; Allow deleting locked files. Default is
                False.
            default_head: Default disk side.
        Return:
            Number of deleted files.
        """
        self._not_closed()
        if default_head is None:
            default_head = self._default_head

        parsed: Optional[List[Tuple[str, Optional[str], Optional[int]]]]
        if pattern is None:
            parsed = None
        elif isinstance(pattern, str):
            parsed = [self.parse_name(pattern, True)]
        else:
            parsed = list(self.parse_name(pat, True) for pat in pattern)

        count = 0
        skipped = 0
        for side in self.sides:
            index = 0
            while index < side.number_of_files:
                entry = side.get_entry(index)
                if entry.match_parsed(parsed, default_head):
                    if not entry.locked or ignore_access:
                        entry.delete(ignore_access)
                        count += 1
                    else:
                        skipped += 1
                        index += 1
                else:
                    index += 1
        if skipped != 0:
            warn(DFSWarning("%s: %d files not deleted"
                            % (self.filename, skipped)))
        return count

    def lock(self, pattern: Union[str, List[str]],
             default_head: int = None) -> int:
        """Lock all files matching pattern.

        Args:
            pattern: Pattern or list or patterns.
        """
        count = 0
        for file in self.get_files(pattern, default_head):
            if not file.locked:
                count += 1
            file.locked = True
        return count

    def unlock(self, pattern: Union[str, List[str]],
               default_head: int = None) -> int:
        """Unlock all files matching pattern.

        Args:
            pattern: Pattern or list or patterns.
        """
        self._not_closed()
        count = 0
        for file in self.get_files(pattern, default_head):
            if file.locked:
                count += 1
            file.locked = False
        return count

    def add_file(self, filename: str, data: bytes, load_addr: int = None,
                 exec_addr: int = None, locked=False, replace=False,
                 ignore_access=False, no_compact=False,
                 default_head: int = None) -> Entry:
        """Add new file to floppy disk image.

        This method raises error if file with the same name already
        exists.

        Args:
            filename: File name.
            data: Data to write to the file.
            load_addr: Optional; New file load address. Default is 0.
            exec_addr: Optional; New file execution address. Default is the same
                as `load_addr`.
            locked: Optional; New file locked flags. Default is False.
            replace: Optional; Allow replacing existing files. Default is False.
            ignore_access: Optional; Allow replacing locked files. Default is
                False.
            no_compact: Optional; Fail if there is no continuous block big
                enough for the file. Otherwise try to compact free
                space. Default is False - i.e. try to compact free
                space if needed.
            default_head: Default disk side.
        Raises:
            IOError: Disk catalog is corrupted.
            FileExistsError: File already exists and 'replace' is false.
            PermissionError: File already exists, is locked and 'ignore_access'
                is false.
            RuntimeError: Disk full or no continuous free block for file.
        """
        self._not_closed()
        # pylint: disable=protected-access
        fullname, head = self.to_fullname(filename, default_head)
        size = len(data)

        # If no side specified and file already exist, try to replace
        if head is None:
            head = next((side.head for side in self.sides
                         if side.find_entry(fullname) is not None), None)

        # If no side specified, find first side which can accommodate the file
        if head is None:
            head = next((side.head for side in self.sides
                         if side.can_add_file(size, no_compact)), None)

        # Won't fit anywhere, just go with side 0
        if head is None:
            head = 0

        side = self.get_side(head)
        return side._add_entry(fullname, data, load_addr, exec_addr, locked,
                               replace, ignore_access, no_compact)

    def import_files(self, os_files: Union[str, List[str]],
                     dfs_names: Union[str, List[str]] = None,
                     inf_mode: int = None,
                     load_addr: int = None, exec_addr: int = None,
                     locked: bool = None,
                     replace=False, ignore_access=False,
                     no_compact=False,
                     continue_on_error=True,
                     verbose=False,
                     default_head: int = None) -> int:
        """Import files from host to floppy image.

        Args:
            os_files: List of files to import or single file name.
            dfs_names: Optional; List of DFS file names or single name. If
                present must have the same number of elements as hostfiles
                parameter.
            inf_mode: Optional; Inf files processing mode:
                - INF_MODE_AUTO - read inf files if present;
                - INF_MODE_ALWAYS - require inf files, fail if not present;
                - INF_MODE_NEVER - treat all files as data files, don't
                    look for extra inf files.
                Default is INF_MODE_AUTO.
            load_addr: Optional; File load address. Applies to all files,
                overrides inf files.
            exec_addr: Optional; File exec address. Applies to all files,
                overrides inf files.
            locked: Optional; File locked attribute. Applies to all files,
                overrides inf files.
            replace: Optional; Allow replacing existing files. Default is False.
            ignore_access: Optional; Allow replacing locked files. Default is
                False.
            no_compact: Optional; Fail if there is no continuous block big
                enough for the files. Otherwise try to compact free space.
                Default is False - i.e. try to compact free space if needed.
            continue_on_error: Optional; Continue on error.
            varbose: Optional; List files as they are being imported.
            default_head: Default disk side.
        """
        import_proc = _ImportFiles(self, os_files, dfs_names, inf_mode,
                                   load_addr, exec_addr, locked, replace,
                                   ignore_access, no_compact, continue_on_error,
                                   verbose, default_head)

        return import_proc.run()

    def _validate_export_params(self, translation, inf_mode, output) -> Tuple:
        self._not_closed()

        if translation is None:
            translation = TRANSLATION_STANDARD

        if inf_mode is None:
            inf_mode = INF_MODE_ALWAYS

        # Get and validate characters translation table
        if not isinstance(translation, bytes):
            if translation == TRANSLATION_STANDARD:
                translation = NAME_STD_TRANS
            elif translation == TRANSLATION_SAFE:
                translation = NAME_SAFE_TRANS
            else:
                raise ValueError("invalid translation mode")
        if isinstance(translation, bytes):
            if len(translation) != 256:
                raise ValueError("translation table must be 256 bytes long")
        else:
            raise ValueError("invalid translation mode")

        # If output ends with directory name, append dfs full name
        if output in ('', '.'):
            output = './'

        _, tail = os.path.split(output)
        if tail == '' or os.path.exists(output) and os.path.isdir(output):
            output = os.path.join(output, '{displayname}')

        return translation, inf_mode, output

    def export_files(self, output: str,
                     files: Union[str, List[str]] = None,
                     create_directories=False,
                     translation: Union[int, bytes] = None,
                     inf_mode: int = None, include_drive=False,
                     replace=False, continue_on_error=True,
                     verbose=False,
                     default_head: int = None) -> int:
        """Export files from floppy image to host.

        Args:
            output: Output directory or file name. This string is
                processed with str.format function with each exported
                file properties (see Entry.PROPERTY_NAMES). If 'output'
                is directory name, it should be terminated with path
                separator (i.e. '/'). In that case dfs full file name
                with be appended to the output path.
            files: List of files or pattern for files to export.
            create_directories: Optional; If True, output directories
                will be automatically created as needed. Otherwise
                this function will fail if output directory doesn't exist.
            translation: Mode for translating dfs filename to host
                filename characters. Can be either ``TRANSLATION_STANDARD``,
                which replaces characters illegal on Windows with underscore
                character or ``TRANLATION_SAFE`` which replaces all characters,
                other than digits and letters, with underscore character.
                Alternatively, caller can provide custom translation table in
                form of ``bytes`` object of length 256 which is, in that case,
                passed directly to ``bytes.translate`` method.
                Default is ``TRANSLATION_STANDARD``.
            inf_mode: Optional; Inf files processing mode:
                - INF_MODE_AUTO - write inf files if load or exec address is not
                    zero, or host file name is different from dfs name;
                - INF_MODE_ALWAYS - always write inf files;
                - INF_MODE_NEVER - never write inf files - file attributes are
                    not preserved.
                Default is INF_MODE_ALWAYS.
            include_drive: Include drive name (i.e. :0. or :2.) in inf
                files created from double sided floppy images. The resulting inf
                files will be incompatible with most software. Use this option
                with care.
            replace: If file with the same name already exists in the output
                directory, it will be replaced with new file. If this option is
                False or not specified, this method will fail.
            continue_on_error: Optional; Continue on error.
            varbose: Optional; List files as they are being exported
            default_head: Disk side. Overrides Image.default_side property.
                If not present, files from both sides are exported.
        """

        export_proc = _ExportFiles(self, output, files, create_directories,
                                   translation, inf_mode, include_drive,
                                   replace, continue_on_error, verbose,
                                   default_head)
        return export_proc.run()

    def compact(self) -> None:
        """Compact fragmented free space on disk.

        Raises:
            IOError: Disk catalog is corrupted
        """
        self._not_closed()
        d_side = self._default_head
        if d_side is not None:
            self.get_side(d_side).compact()
        else:
            for side in self.sides:
                side.compact()

    def format(self) -> None:
        """Format default side or both sides."""
        self._not_closed()
        d_side = self._default_head
        if d_side is not None:
            self.get_side(d_side).format()
        else:
            for side in self.sides:
                side.format()

    def _validate_copy_over(self, source: 'Image', default_head: Optional[int]):

        if not isinstance(source, Image):
            raise ValueError("source must be Image")

        # pylint: disable = protected-access
        self._not_closed()
        source._not_closed()

        # Source and destination can be the same file if we copy from one side to the other
        if os.path.sameopenfile(self.file.fileno(),  # type: ignore[union-attr]
                                source.file.fileno()):  # type: ignore[union-attr]
            if (default_head is None or source._default_head is None or
                    default_head == source._default_head):
                raise ValueError("source and destination is the same image file")

    def _validate_backup(self, source: 'Image', default_head: Optional[int]):

        self._validate_copy_over(source, default_head)

        if source.tracks > self.tracks:
            raise ValueError("cannot copy 80 tracks floppy to 40 tracks.")

    def backup(self, source: 'Image', default_head: int = None):
        """Copy all sectors data from other image.

        Args:
            source: Image object to copy from.
            default_head: Destination (this) disk side. Overrides
                Image.default_side property. If not present, both sides are
                copied from source.
        """

        if default_head is None:
            default_head = self._default_head

        self._validate_backup(source, default_head)

        if source._default_head is not None:
            source_sides: Tuple[Side, ...] = (source.sides[source._default_head],)
        else:
            source_sides = source.sides

        if default_head is not None:
            dest_sides: Tuple[Side, ...] = (self.sides[default_head],)
        else:
            dest_sides = self.sides

        if len(source_sides) > len(dest_sides):
            raise ValueError("source side must be selected.")

        if len(source_sides) < len(dest_sides):
            raise ValueError("destination side must be selected.")

        for src, dst in zip(source_sides, dest_sides):
            dst.get_all_sectors().writeall(src.get_all_sectors())

        self.validate()

    def copy_over(self, source: 'Image', pattern: Union[str, List[str]],
                  replace=False, ignore_access=False, no_compact=False,
                  change_dir=False, preserve_attr=False,
                  continue_on_error=True, verbose=False,
                  default_head: int = None) -> int:
        """Copy files over from other image.

        Args:
            source: Source image.
            pattern: Pattern or list or patterns.
            replace: Optional; Allow replacing existing files. Default is False.
            ignore_access: Optional; Allow replacing locked files. Default is
                False.
            no_compact: Optional; Fail if there is no continuous block big
                enough for the files. Otherwise try to compact free space.
                Default is False - i.e. try to compact free space if needed.
            preserve_attr: Optional; Preserve locked attribute on copied files.
            continue_on_error: Optional; Continue on error.
            varbose: Optional; List files as they are being imported.
            default_head: Default target disk side.
        """

        count = 0

        if default_head is None:
            default_head = self._default_head

        self._validate_copy_over(source, default_head)

        files = source.get_files(pattern)

        for file in files:

            inf = file.get_inf()
            inf.filename, inf.drive = self.to_fullname(
                file.fullname if not change_dir else file.filename)
            inf.locked = file.locked and preserve_attr

            try:
                # Read file data
                data = file.readall()

                # Add file to disk image
                self.add_file(inf.filename, data, file.load_address,
                              file.exec_address,
                              locked=inf.locked, replace=replace,
                              ignore_access=ignore_access,
                              no_compact=no_compact)

                if verbose:
                    print("%-40s <- %s" % (str(inf), source.filename))

                count += 1

            except (FileExistsError, PermissionError, OSError) as err:
                if not continue_on_error:
                    raise
                warn(DFSWarning(str(err)))

            except (RuntimeError) as err:
                if not continue_on_error:
                    raise
                warn(DFSWarning(str(err)))
                break

        if len(files) != count:
            warn(DFSWarning("%s: %d files not copied"
                            % (self.filename, len(files) - count)))
        return count

    @classmethod
    def create(cls, fname: str, heads: int = None, tracks: int = None,
               linear: bool = None) -> 'Image':
        """Create new image file.

        Created Image object keeps open file handle to the disk image file, so make sure
        to call the 'close()' method when your program finishes using the created object,
        or even better use the 'with' statement.

        Example:
            ::
                with Image.create("image.ssd") as image:
                    image.get_side(0).import(glob.glob("srcdir/*"))

        Args:
            fname: Image file name.
            heads: Optional; Number of sides - 1, 2. Default is based on file name.
            tracks: Optional; Number of tracks per side - 80 or 40. Default is 80.
            linear: Optional; This flags is always True for single sided disks.
                For double sided disks, it indicates, that data for each side is grouped
                together as opposed to more popular image format where track data for
                two sides are interleaved. Default is True for double sided SSD images
                and False for other double sided disks.
        Raises:
            ValueError: If 'heads' or 'tracks' argument has invalid value.
        Returns:
            New 'Image' object.
        """
        # Default to single side if file extension is not 'dsd'
        if heads is None:
            if fname.lower().endswith(".dsd"):
                heads = 2
            else:
                heads = 1

        # Default to 80 tracks
        if tracks is None:
            tracks = DOUBLE_TRACKS

        # Dual sided images with ssd extension are linear by default
        if linear is None:
            linear = bool(fname.lower().endswith(".ssd"))

        # Single sided images are always linear
        if heads == 1:
            linear = True

        new_image = Image(fname, heads, tracks, linear)
        try:
            new_image.original_size = 0
            new_image.isvalid = True

            new_image.is_read_only = False
            for side in new_image.sides:
                side.format(tracks)

            new_image.file = open(fname, "xb")
            new_image.is_new_image = True
        except:  # noqa: E722
            new_image.close()
            raise

        return new_image

    @classmethod
    def _peek_number_of_tracks(cls, fname) -> int:
        catalog_data = bytearray(CATALOG_SECTORS * SECTOR_SIZE)
        with open(fname, 'rb') as file:
            file.readinto(catalog_data)  # type: ignore[attr-defined]
        sectors = catalog_data[263] + ((catalog_data[262] & 3) << 8)
        if sectors == SINGLE_TRACKS * SECTORS:
            return SINGLE_TRACKS
        return DOUBLE_TRACKS

    @classmethod
    def _validate_minimal_size(cls, heads, fsize):

        # Make sure that at least first side catalog sectors are present
        if fsize < CATALOG_SECTORS * SECTOR_SIZE:
            raise RuntimeError("disk image too small")

        if heads is not None and (heads < 1 or heads > 2):
            raise ValueError("invalid number of disc sides")

        # Sanity check - image file size should be multiple of sector size
        if fsize % SECTOR_SIZE != 0:
            raise RuntimeError("invalid disk image size")

    @classmethod
    def _get_image_format(cls, fname: str, heads: Optional[int],
                          tracks: Optional[int],
                          linear: Optional[bool]) -> Tuple[int, int, int, bool]:

        fsize = os.path.getsize(fname)

        cls._validate_minimal_size(heads, fsize)

        # Default to single side unless file extension is 'dsd' or image is bigger that
        # max. single sided image
        if heads is None:
            heads = (2 if fname.lower().endswith(".dsd") or fsize > TRACK_SIZE * DOUBLE_TRACKS
                     else 1)

        # Default to 80 tracks
        if tracks is None:
            tracks = (DOUBLE_TRACKS if fsize <= SINGLE_TRACKS * SECTORS * SECTOR_SIZE * heads
                      else cls._peek_number_of_tracks(fname))

        # Dual sided images with 'ssd' extension are linear by default
        if linear is None:
            linear = fname.lower().endswith(".ssd")

        # Single sided images are always linear
        if heads == 1:
            linear = False

        # If double sided, make sure second side catalog sectors are present
        if heads == 2:
            if not linear:
                if fsize < TRACK_SIZE + CATALOG_SECTORS * SECTOR_SIZE:
                    raise RuntimeError("disk image too small for %s"
                                       % Image.sides_and_tracks_str(heads, tracks))
            else:
                if fsize < tracks * TRACK_SIZE + CATALOG_SECTORS * SECTOR_SIZE:
                    raise RuntimeError("disk image too small for linear %s"
                                       % Image.sides_and_tracks_str(heads, tracks))

        return fsize, heads, tracks, linear

    @classmethod
    def _load(cls, filename: str, for_write: bool = False,
              heads: int = None, tracks: int = None,
              linear: bool = None, warning_mode: int = None) -> 'Image':
        """Open file handle and load image file.

        Args:
            filename: File name.
            for_write: Optional; Open image for write.
            heads: Optional; Number of sides - 1 or 2. Default based on file name and size.
            tracks: Optional; Number of tracks per side - 80 or 40. Default is 80.
            linear: Optional; This flags is always True for single sided disks.
                For double sided disks, it indicates, that data for each side is grouped
                together as opposed to more popular image format where track data for
                two sides are interleaved. Default is True for double sided SSD images
                and False for other double sided disks.
            warning_mode: Optional; Warning mode for validation: WARN_FIRST - display
                warning for first non-fatal validation error and stop validation, WARN_ALL -
                display all validation errors, WARN_NONE - don't display validation errors.
        Raises:
            RuntimeError: If image file is invalid or the class doesn't like it
                for some reason.
            ValueError: If 'heads' or 'tracks' argument has invalid value.
        Returns:
            New 'Image' object.
        """
        # pylint: disable=protected-access
        fname_base = os.path.basename(filename)
        fname = os.path.abspath(filename)

        if warning_mode is None:
            warning_mode = WARN_FIRST

        # pylint: disable=unused-argument
        def formatmsg(message: Union[Warning, str]) -> str:
            return "%s: %s: %s" % (type(message).__name__, fname_base, str(message))

        try:
            simplewarn.current_format = formatmsg

            fsize, heads, tracks, linear = cls._get_image_format(fname, heads,
                                                                 tracks, linear)

            # Create new 'Image' object and read file contents
            new_image = Image(fname, heads, tracks, linear)
            try:
                new_image.path = fname
                new_image.original_size = fsize

                mode_str = "rb+" if for_write else "rb"
                new_image.file = open(fname, mode_str)
                new_image.is_read_only = not for_write
                new_image.file.readinto(new_image._data)  # type: ignore[attr-defined]

                # Sanity check
                if fsize > new_image.max_size:
                    raise RuntimeError("disk image too big for %s" %
                                       Image.sides_and_tracks_str(heads, tracks))

                # Validate the image
                new_image.validate(warning_mode)

                # Sanity check. Validate the image first to know how to calculate min_size
                if fsize < new_image.min_size:
                    raise RuntimeError("disk image too small")
            except:  # noqa: E722
                new_image.close(False)
                raise

        except RuntimeError as err:
            if len(err.args) > 0:
                err.args = (fname_base + ": " + err.args[0], )
            raise

        finally:
            simplewarn.current_format = simplewarn.formatmsg

        return new_image

    @classmethod
    def open(cls, filename: str, for_write: bool = False, open_mode: int = None,
             heads: int = None, tracks: int = None, linear: bool = None,
             warning_mode: int = None) -> 'Image':
        """Open disk image file.

        Created Image object keeps open file handle to the disk image file, so make sure
        to call the 'close()' method when your program finishes using the created object,
        or even better use the 'with' statement.

        Example:
            ::
                with Image.open("image.ssd") as image:
                    image.cat()

        Args:
            filename: Disk image file name.
            for_write: Optional; Open image for write.
            open_mode: Optional; File open mode. Can be one of: OPEN_MODE_ALWAYS - create
                new or open existing file, OPEN_MODE_NEW - create new file, fail if file
                already exists, OPEN_MODE_EXISTING - open existing file, fail if file
                doesn't exist. Default is OPEN_MODE_ALWAYS.
            heads: Optional; Number of sides - 1 or 2. Default based on file name and size.
            tracks: Optional; Number of tracks per side - 80 or 40. Default is 80.
            linear: Optional; This flags is always True for single sided disks.
                For double sided disks, it indicates, that data for each side is grouped
                together as opposed to more popular image format where track data for
                two sides are interleaved. Default is True for double sided SSD images
                and False for other double sided disks.
            warning_mode: Optional; Warning mode for validation: WARN_FIRST - display
                warning for first non-fatal validation error and stop validation, WARN_ALL -
                display all validation errors, WARN_NONE - don't display validation errors.
        Raises:
            RuntimeError: If image file is invalid or the class doesn't like it
                for some reason.
            ValueError: If 'heads' or 'tracks' argument has invalid value.
            ValueError: If 'open_mode' is invalid or 'open_mode' is OPEN_MODE_NEW
                and 'for_write' is False.
            FileNotFoundError: File not found and open_mode is OPEN_MODE_EXISTING or
                for_write is False.
            FileExistsError: File already exists and open_mode is OPEN_MODE_NEW.
        Returns:
            New 'Image' object.
        """
        if open_mode is None:
            open_mode = OPEN_MODE_ALWAYS

        if (open_mode not in (OPEN_MODE_ALWAYS, OPEN_MODE_EXISTING, OPEN_MODE_NEW) or
                open_mode == OPEN_MODE_NEW and not for_write):
            raise ValueError("invalid open mode")

        if open_mode != OPEN_MODE_NEW:
            try:
                return cls._load(filename, for_write, heads, tracks, linear, warning_mode)
            except FileNotFoundError:
                if open_mode == OPEN_MODE_EXISTING or not for_write:
                    raise

        return cls.create(filename, heads, tracks, linear)

    def save(self, size_option: int = None) -> None:
        """Write image data back to file.

        Args:
            size_option: Optional; File size option:
                - SIZE_OPTION_KEEP (0) - Keep size, possibly expanding as needed.
                - SIZE_OPTION_EXPAND (1) - Expand to maximum size.
                - SIZE_OPTION_SHRINK (2) - Shrink to minimum size to include last used sector.
        """
        self._not_closed()
        if self.file is None or self.is_read_only:
            return
        size = self.__get_size_for_save(size_option)
        self.file.seek(0, SEEK_SET)
        self.file.write(self._data[:size])
        if size_option == SIZE_OPTION_SHRINK:
            self.file.truncate(size)
        self.modified = False
        self.original_size = size

    def close(self, save: bool = True):
        """Close and invalidate object.

        Args:
            save: Optional; Write data back to image file if image is not open
                for read only, and data has been modified.
        """
        if self.file is not None:
            if save and not self.is_read_only and self.modified:
                self.save()
            self.file.close()
            self.file = None
            if self.is_new_image and not save:
                os.remove(self.path)

        self._data = cast(bytearray, None)
        self.dataview = cast(memoryview, None)

        # This may be redundant, but it won't hurt
        if self.sides is not None:
            for side in self.sides:
                side.csector1 = cast(memoryview, None)
                side.csector2 = cast(memoryview, None)
                side.image = cast(ImageProtocol, None)
            self.sides = cast(Tuple[Side, ...], None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(exc_type is None)
        return False


class _ImportFiles:

    def __init__(self, image: Image, os_files: Union[str, List[str]],
                 dfs_names: Optional[Union[str, List[str]]],
                 inf_mode: Optional[int], load_addr: Optional[int],
                 exec_addr: Optional[int], locked: Optional[bool],
                 replace: bool, ignore_access: bool,
                 no_compact: bool, continue_on_error: bool,
                 verbose: bool, default_head: Optional[int]):
        image._not_closed()

        if default_head is None:
            default_head = image._default_head

        if inf_mode is None:
            inf_mode = INF_MODE_AUTO
        if inf_mode not in (INF_MODE_ALWAYS, INF_MODE_AUTO, INF_MODE_NEVER):
            raise ValueError('invalid inf mode')

        if isinstance(os_files, str):
            os_files = [os_files]

        if dfs_names is not None:
            if isinstance(dfs_names, str):
                dfs_names = [dfs_names]
            if len(dfs_names) != len(os_files):
                raise ValueError("size of dfs_names parameter doesn't match "
                                 "number of files to import")

        self.image = image
        self.os_files: List[str] = os_files
        self.dfs_names: Optional[List[str]] = dfs_names
        self.inf_mode: int = inf_mode
        self.load_addr = load_addr
        self.exec_addr = exec_addr
        self.locked = locked
        self.replace = replace
        self.ignore_access = ignore_access
        self.no_compact = no_compact
        self.continue_on_error = continue_on_error
        self.verbose = verbose
        self.default_head: Optional[int] = default_head
        self.filelist: List[Dict] = []

    def _scan_inf_files(self):
        index = 0
        inf_cache = InfCache()
        fileset: Set[str] = set()
        for file in self.os_files:
            displayfile = file
            host_file = None
            inf = None
            dfs_name = self.dfs_names[index] if self.dfs_names is not None else None
            basename = os.path.basename(file)

            if os.path.isdir(file):
                warn(DFSWarning("skipping directory '%s'" % file))
                index += 1
                continue

            # Inf file passed - get data file
            if self.inf_mode != INF_MODE_NEVER and file.lower().endswith(".inf"):
                inf = inf_cache.get_inf_by_inf_file(file)
                if inf is not None:
                    displayfile = displayfile[:-4]
                    host_file = inf.inf_path[:-4]

            # Data file passed - try to find inf file
            if self.inf_mode != INF_MODE_NEVER and inf is None:
                inf = inf_cache.get_inf_by_host_file(file)
                if inf is not None:
                    host_file = inf.inf_path[:-4]

            # Inf file not found
            if host_file is None:
                host_file = canonpath(file)
                if self.inf_mode == INF_MODE_ALWAYS:
                    raise ValueError("missing inf file for %s" % host_file)

            # Add file if not already encountered
            if host_file not in fileset:
                fileset.add(host_file)
                filedict = {'displayname': displayfile, 'hostfile': host_file, 'basename': basename,
                            'dfs_name': dfs_name, 'inf': inf}
                self.filelist.append(filedict)

            index += 1

    def _import_file(self, displayname: str, hostfile: str, basename: str,
                     dfs_name: str, inf: Optional[Inf]):
        load_addr = self.load_addr
        exec_addr = self.exec_addr
        locked = self.locked

        # Update with attributes from inf file if present
        if inf is not None:
            if load_addr is None:
                load_addr = inf.load_addr
            if exec_addr is None:
                exec_addr = inf.exec_addr
            if locked is None:
                locked = inf.locked
            if dfs_name is None:
                dfs_name = inf.filename

        # Exec addr defaults to load addr
        if exec_addr is None:
            exec_addr = load_addr

        # If dfs name is not given, use host file name
        if dfs_name is None:
            dfs_name = basename

        # Read file data
        with open(hostfile, "rb") as file:
            data = file.read()

        # Add file to disk image
        entry = self.image.add_file(dfs_name, data, load_addr, exec_addr,
                                    locked=locked, replace=self.replace,
                                    ignore_access=self.ignore_access,
                                    no_compact=self.no_compact,
                                    default_head=self.default_head)

        if self.verbose:
            new_inf = entry.get_inf()
            if inf is not None:
                src_name = "%s, %s" % (displayname, os.path.basename(inf.inf_path))
            else:
                src_name = displayname
            print("%-40s <- %s" % (str(new_inf), src_name))

    def run(self) -> int:
        """Run import process"""
        count = 0
        self._scan_inf_files()
        for filedict in self.filelist:
            try:
                self._import_file(**filedict)
                count += 1

            except (FileExistsError, PermissionError, OSError) as err:
                if not self.continue_on_error:
                    raise
                warn(DFSWarning(str(err)))

            except (RuntimeError) as err:
                if not self.continue_on_error:
                    raise
                warn(DFSWarning(str(err)))
                break

        if count != len(self.filelist):
            warn(DFSWarning("%s: %d files not imported"
                            % (self.image.filename, len(self.filelist) - count)))

        return count


class _ExportFiles:

    def __init__(self, image: Image, output: str,
                 files: Optional[Union[str, List[str]]],
                 create_directories: bool,
                 translation: Optional[Union[int, bytes]],
                 inf_mode: Optional[int], include_drive: bool,
                 replace: bool, continue_on_error: bool,
                 verbose: bool, default_head: Optional[int]):
        image._not_closed()

        if translation is None:
            translation = TRANSLATION_STANDARD

        if inf_mode is None:
            inf_mode = INF_MODE_ALWAYS

        if inf_mode not in (INF_MODE_ALWAYS, INF_MODE_AUTO, INF_MODE_NEVER):
            raise ValueError('invalid inf mode')

        # Get and validate characters translation table
        if not isinstance(translation, bytes):
            if translation == TRANSLATION_STANDARD:
                translation = NAME_STD_TRANS
            elif translation == TRANSLATION_SAFE:
                translation = NAME_SAFE_TRANS
            else:
                raise ValueError("invalid translation mode")

        if len(translation) != 256:
            raise ValueError("translation table must be 256 bytes long")

        # If output ends with directory name, append dfs full name
        if output in ('', '.'):
            output = './'

        _, tail = os.path.split(output)
        if tail == '' or os.path.exists(output) and os.path.isdir(output):
            output = os.path.join(output, '{displayname}')

        self.image = image
        self.output = output
        self.files = files
        self.create_directories = create_directories
        self.translation: bytes = translation
        self.inf_mode: int = inf_mode
        self.include_drive = include_drive
        self.replace = replace
        self.continue_on_error = continue_on_error
        self.verbose = verbose
        self.default_head = default_head
        self.inf_cache = InfCache()
        self.output_set: Set[str] = set()

    def _inf_file_clash(self, path: str, inf: Inf, dfs_name: str,
                        just_created: bool) -> bool:
        """Returns True to overwrite, False to generate next available filename."""

        # Inf path exists, check if it's the same dfs name
        if inf.filename == dfs_name:

            # Already exists for the same dfs name
            if not self.replace and just_created:
                raise FileExistsError("not overwriting file '%s', just created for ':%d.%s'"
                                      % (path, inf.drive, inf.filename))

            if not self.replace:
                raise FileExistsError("file '%s' already exists for '%s'"
                                      % (path, inf.filename))

            if just_created:
                warn(DFSWarning("overwriting file '%s', just created for ':%d.%s'"
                                % (path, inf.drive, inf.filename)))

            return True

        # Different DFS name, don't overwrite
        return False

    def _data_file_clash(self, path: str, just_created: bool) -> bool:
        """Returns True to overwrite, or raises exception if 'replace' is not on."""

        # Data file exists.
        if not self.replace and just_created:
            raise FileExistsError("not overwriting just created file '%s'" % path)

        if not self.replace:
            raise FileExistsError("file '%s' already exists" % path)

        if just_created:
            warn(DFSWarning("overwriting just created file '%s'" % path))

        return True

    def _find_available(self, dirname: str, filename: str, dfs_name: str,
                        inf_mode: int) -> Tuple[str, Optional[str]]:
        """Find available host filename, append numbers if needed."""

        done = False
        index = 0
        check_name: Optional[str] = filename
        use_inf = inf_mode == INF_MODE_ALWAYS

        while not done:
            path = os.path.join(dirname, cast(str, check_name))
            canon = canonpath(path)
            just_created = canon in self.output_set
            inf_path = None

            if inf_mode != INF_MODE_NEVER:
                inf: Optional[Inf] = self.inf_cache.get_inf_by_host_file(path)
            else:
                inf = None

            if inf is not None:
                # Inf file exists.
                if self._inf_file_clash(path, inf, dfs_name, just_created):
                    inf_path = inf.inf_path
                    break
                # Force using inf and generate next name
                use_inf = True

            elif os.path.exists(path):
                # Data file exists.
                self._data_file_clash(path, just_created)
                break

            else:
                # Name free to use
                break

            # Generate next name
            index += 1
            check_name = "%s-%02d" % (filename, index)

        if not use_inf:
            return path, None

        if inf_path is None:
            inf_path = "%s.inf" % path

        return path, inf_path

    def _get_output_name(self, entry: Entry) -> str:
        # Get file properties to build file name
        props = entry.get_properties(True)
        props["fullname"] = (entry.fullname_bytes.translate(self.translation)
                             .lstrip().decode("ascii"))
        props["filename"] = (entry.filename_bytes.translate(self.translation)
                             .decode("ascii"))
        props["directory"] = (entry.directory_bytes.translate(self.translation)
                              .decode("ascii"))
        props["displayname"] = (entry.displayname_bytes.translate(self.translation)
                                .lstrip().decode("ascii"))
        return self.output.format_map(props)

    def _needs_inf(self, entry: Entry, output_name: str, dfs_name: str) -> bool:
        if self.inf_mode != INF_MODE_AUTO:
            return False
        if os.path.basename(output_name) != dfs_name:
            return True
        if entry.load_address != 0 or entry.exec_address != 0 or entry.locked:
            return True
        return False

    def _ensure_directory(self, dirname: str) -> bool:
        # Check if directory exists
        if dirname != '' and not os.path.exists(dirname):
            if not self.create_directories:
                if not self.continue_on_error:
                    raise FileNotFoundError("output directory '%s' doesn't exist" % dirname)

                warn(DFSWarning("output directory '%s' doesn't exist" % dirname))
                return False

            os.makedirs(dirname)
            print("created directory '%s'" % dirname)

        return True

    def _export_entry(self, entry: Entry) -> bool:

        output_name = self._get_output_name(entry)

        # Name to put in inf
        if len(self.image.sides) != 1 and self.include_drive:
            dfs_name = ":%d.%s" % (entry.drive, entry.fullname_ascii.lstrip())
        else:
            dfs_name = entry.fullname_ascii.lstrip()

        # Enable inf for auto mode if required
        inf_mode = self.inf_mode
        if self._needs_inf(entry, output_name, dfs_name):
            inf_mode = INF_MODE_ALWAYS

        # Check if file exists
        dirname, filename, = os.path.split(output_name)
        try:
            data_name, inf_name = self._find_available(dirname, filename,
                                                       dfs_name, inf_mode)
        except FileExistsError as err:
            if not self.continue_on_error:
                raise
            warn(DFSWarning(str(err)))
            return False

        data = entry.readall()
        inf = entry.get_inf()
        inf.filename = dfs_name

        if not self._ensure_directory(dirname):
            return False

        with open(data_name, "wb") as file:
            file.write(data)

        if inf_name is not None:
            inf.inf_path = canonpath(inf_name)
            inf.save()
            # Twice (!) to update canonical path form
            inf.inf_path = canonpath(inf_name)
            self.inf_cache.update(inf.inf_path, inf)

        if self.verbose:
            if inf_name is not None:
                v_name = "%s, %s" % (data_name, os.path.basename(inf_name))
            else:
                v_name = data_name
            print("%-40s -> %s" % (str(inf), v_name))

        self.output_set.add(canonpath(data_name))

        return True

    def run(self) -> int:
        """Run export process"""
        entries = self.image.get_files(self.files, self.default_head)
        count = 0
        skipped = 0
        for entry in entries:
            if self._export_entry(entry):
                count += 1
            else:
                skipped += 1

        if skipped != 0:
            warn(DFSWarning("%s: %d files not exported"
                            % (self.image.filename, skipped)))

        return count
