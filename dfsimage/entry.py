"""Access to single file entry structure in disk catalog sectors."""

import sys
import hashlib
from typing import Optional, Union, Sequence, Dict
from typing import cast

from .simplewarn import warn
from .consts import SECTOR_SIZE, CATALOG_SECTORS
from .consts import DIGEST_MODE_ALL, DIGEST_MODE_USED, DIGEST_MODE_FILE, DIGEST_MODE_DATA
from .consts import LIST_FORMAT_CAT, LIST_FORMAT_INF, LIST_FORMAT_INFO, LIST_FORMAT_RAW
from .consts import LIST_FORMAT_JSON, LIST_FORMAT_XML, LIST_FORMAT_TABLE
from .misc import bchr, ValidationWarning, LazyString, json_dumps, xml_dumps
from .conv import bbc_to_unicode, unicode_to_bbc

from .pattern import ParsedPattern, PatternList, PatternUnion
from .sectors import Sectors
from .inf import Inf
from .protocol import SideProtocol, Property


class Entry:
    """Provides access to single file entry structure in disk catalog sectors."""

    # Translation for sorting file names in DFS - capital and small letters
    # are grouped together
    SORTING_TRANSLATION = bytes(
        # codes below 'A' or above 'z' - leave alone
        x if x <= ord('A') or x > ord('z') else
        # capital letters - spread by one position each
        x * 2 - 0x41 if x <= ord('Z') else
        # codes '[' to '`' - move above letters
        x + 26 if x < ord('a') else
        # small letters - shuffle with capitals
        x * 2 - 0x80
        for x in range(0, 256)
        )

    TABLE_FORMAT = (
        "{image_filename:12}|{drive}|{index:2}|"
        "{fullname:9}|{access:1}|"
        "{load_addr:06X}|{exec_addr:06X}|{size:06X}|"
        "{sha1_data}"
        )

    def __init__(self, side: SideProtocol, index: int,
                 entry1: memoryview, entry2: memoryview) -> None:
        """Construct 'Catalog' object referencing catalog sectors of a disk image side.

        Args:
            side: Parent 'Side' object.
            index: File entry index in range 0 - 30.
            entry1: A 'memoryview' to file entry part in first catalog sector.
            entry2: A 'memoryview' to file entry part in second catalog sector.
        """
        self.side = side
        self.index = index
        self.entry1 = entry1
        self.entry2 = entry2
        self.__name_cache: Optional[bytes] = None
        self.__name_seq: Optional[int] = None

    @staticmethod
    def isnamechar(char: int) -> bool:
        """Validate file name character.

        Check if ASCII code belongs to range 32 - 126. Even though characters
        such as ':', '.' and '|' may be pose a problem for DFS, they are not
        considered invalid by this module.

        Args:
            c: ASCII code of the character.
        Returns:
            A boolean indicating if the character is valid.
        """
        return 32 <= char < 127

    @property
    def directory_bytes(self) -> bytes:
        """File directory name as raw bytes."""
        return bchr(self.entry1[7] & 127)

    @directory_bytes.setter
    def directory_bytes(self, value: bytes) -> None:
        if len(value) != 1 or not Entry.isnamechar(value[0]):
            raise ValueError("invalid directory name")
        self.side.modified = True
        self.entry1[7] = (self.entry1[7] & 128) | value[0]  # type: ignore

    def __get_directory(self, pure_ascii: bool = False) -> str:
        directory = self.directory_bytes.decode("ascii")
        if pure_ascii:
            return directory
        return bbc_to_unicode(directory)

    @property
    def directory(self) -> str:
        """File directory name.

        Directory name is a single character. Default directory name is '$'.

        Raises:
            ValueError: Assigned name is invalid or longer than 1 char.
        """
        return self.__get_directory()

    @directory.setter
    def directory(self, value: str) -> None:
        self.directory_bytes = unicode_to_bbc(value).ljust(1, "$").encode("ascii")

    @property
    def filename_bytes(self) -> bytes:
        """File name as raw bytes."""
        return bytes(x & 127 for x in self.entry1[0:7]).rstrip(b' ')

    @filename_bytes.setter
    def filename_bytes(self, value: bytes) -> None:
        value = value.ljust(7)
        if len(value) != 7 or any(not Entry.isnamechar(x) for x in value):
            raise ValueError("invalid file name")
        self.side.modified = True
        self.entry1[0:7] = value  # type: ignore

    def __get_filename(self, pure_ascii: bool = False) -> str:
        value = self.filename_bytes.decode("ascii")
        if pure_ascii:
            return value
        return bbc_to_unicode(value)

    @property
    def filename(self) -> str:
        """File name string not including directory name.

        File name is up to 7 characters long.

        Raises:
            ValueError: Assigned name is invalid or longer than 7 chars.
        """
        return self.__get_filename()

    @filename.setter
    def filename(self, value: str) -> None:
        self.filename_bytes = unicode_to_bbc(value).encode("ascii")

    @property
    def fullname_bytes(self) -> bytes:
        """Raw full file name including directory name as bytes."""
        return b'%s.%s' % (self.directory_bytes, self.filename_bytes)

    def __get_fullname(self, pure_ascii: bool = False) -> str:
        value = self.fullname_bytes.decode("ascii")
        if pure_ascii:
            return value
        return bbc_to_unicode(value)

    @property
    def fullname(self) -> str:
        """Full file name including directory name.

        Raises:
            ValueError: Assigned name is invalid or too long.
        """
        return self.__get_fullname(False)

    @fullname.setter
    def fullname(self, value: str) -> None:
        value = self.side.to_fullname(value)
        if len(value) > 1 and value[1] == '.':
            self.directory, _, self.filename = value.partition('.')
        else:
            ValueError("invalid file name '%s'" % value)

    @property
    def fullname_ascii(self) -> str:
        """Full file name without pound character translation.

        Full file name including directory name, without translation
        of BBC's ASCII code &60 to Unicode pound sign.

        Raises:
            ValueError: Assigned name is invalid or too long.
        """
        return self.__get_fullname(True)

    @property
    def displayname_bytes(self) -> bytes:
        """Name as displayed by CAT as raw bytes."""
        if self.directory == self.side.image.current_dir:
            return self.filename_bytes
        return b'%s.%s' % (self.directory_bytes, self.filename_bytes)

    def __get_displayname(self, pure_ascii: bool = False) -> str:
        value = self.displayname_bytes.decode("ascii")
        if pure_ascii:
            return value
        return bbc_to_unicode(value)

    @property
    def displayname(self) -> str:
        """Name as displayed by CAT.

        Short name if file is in current directory, otherwise fullname.'
        """
        return self.__get_displayname(False)

    @property
    def rawname(self) -> bytes:
        """Get raw file name from catalog entry.

        This property is used for calculating disk digest.
        """
        return bytes((x & 0x7f for x in self.entry1))

    @property
    def sorting_string(self) -> bytes:
        """Full file name translated for sorting. Not usable otherwise."""
        if self.__name_cache is None or self.__name_seq != self.side.image.mod_seq:
            dirname = bchr(self.entry1[7] & 127).translate(Entry.SORTING_TRANSLATION)
            filename = bytes(x & 127 for x in self.entry1[0:7]).translate(Entry.SORTING_TRANSLATION)
            self.__name_cache = dirname + filename
            self.__name_seq = self.side.image.mod_seq
        return self.__name_cache

    @property
    def locked(self) -> bool:
        """File locked attribute.

        Files with locked attribute are protected from modification
        or deletion by Disk Filing System. This module doesn't respect that.
        """
        return bool((self.entry1[7] >> 7) & 1)

    @locked.setter
    def locked(self, value: bool) -> None:
        bitval = 128 if value else 0
        self.side.modified = True
        self.entry1[7] = (self.entry1[7] & 127) | bitval  # type: ignore

    @property
    def access(self) -> str:
        """File access mode - "L" if file is locked, empty otherwise"""
        return "L" if self.locked else ""

    @property
    def load_address(self) -> int:
        """File load address."""
        high = self.get_high_bits(1)
        if high == 3:
            high = 255
        return Entry.get_word(self.entry2[0:2]) | (high << 16)

    @load_address.setter
    def load_address(self, value: int) -> None:
        high = (value >> 16) & 3
        self.side.modified = True
        Entry.set_word(self.entry2[0:2], value & 0xFFFF)
        self.set_high_bits(1, high)

    @property
    def exec_address(self) -> int:
        """File execution address."""
        high = self.get_high_bits(3)
        if high == 3:
            high = 255
        return Entry.get_word(self.entry2[2:4]) | (high << 16)

    @exec_address.setter
    def exec_address(self, value: int) -> None:
        high = (value >> 16) & 3
        self.side.modified = True
        Entry.set_word(self.entry2[2:4], value & 0xFFFF)
        self.set_high_bits(3, high)

    @property
    def size(self) -> int:
        """File length in bytes."""
        high = self.get_high_bits(2)
        return Entry.get_word(self.entry2[4:6]) | (high << 16)

    @size.setter
    def size(self, value: int) -> None:
        high = (value >> 16) & 3
        self.side.modified = True
        Entry.set_word(self.entry2[4:6], value & 0xFFFF)
        self.set_high_bits(2, high)

    @property
    def start_sector(self) -> int:
        """Logical number of the first sector containing file data."""
        high = self.get_high_bits(0)
        return self.entry2[7] | (high << 8)

    @start_sector.setter
    def start_sector(self, value: int) -> None:
        high = (value >> 8) & 3
        self.side.modified = True
        self.entry2[7] = value & 0xFF  # type: ignore
        self.set_high_bits(0, high)

    @property
    def sectors_count(self) -> int:
        """Number of sectors occupied by file data based on file length."""
        return (self.size + SECTOR_SIZE - 1) // SECTOR_SIZE

    @property
    def end_sector(self) -> int:
        """Logical number of the first sector after sectors containing file data."""
        return self.start_sector + self.sectors_count

    @property
    def head(self) -> int:
        """Head - 0 or 1."""
        return self.side.head

    @property
    def drive(self) -> int:
        """Entry drive - 0 or 2"""
        return self.side.head * 2

    def get_sectors(self) -> Sectors:
        """Get 'Sectors' object for sectors occupied by this file.

        Raises:
            IndexError: The 'self' object points to a catalog entry beyond last
                used entry or disk catalog is invalid.
        """
        if self.index >= self.side.number_of_files:
            raise IndexError("file entry index out of range")
        return self.side.get_logical_sectors(self.start_sector, self.end_sector, self.size)

    def readall(self) -> bytes:
        """Read all file data and return 'bytes' object.

        Raises:
            IndexError: The 'self' object points to a catalog entry beyond last
                used entry or disk catalog is invalid.
        """
        return self.get_sectors().readall()

    def writeall(self, data: Union[bytes, Sequence[int], 'Sectors']) -> None:
        """Write all file data.

        Args:
            data: A 'bytes' object or other iterable object.
        Note:
            This function doesn't update catalog entry in any way. File size
            and sectors allocation should be managed by the caller.
        Raises:
            IndexError: The 'self' object points to a catalog entry beyond last
                used entry or disk catalog is invalid.
            ValueError: Data is larger that file size.
        """
        self.get_sectors().writeall(data)

    def hexdump(self, start: int = None, size: int = None, width: int = None,
                ellipsis: bool = None, file=sys.stdout) -> None:
        """Hexdecimal dump of file data.

        Args:
            start: Optional; Starting offset.
            size: Optional; Number of bytes to dump.
            width: Optional; Number of bytes per line.
            ellipsis: Optional; If ellipsis is True, repeating lines will be skipped.
            file: Output stream. Default is sys.stdout.
        Raises:
            IndexError: The 'self' object points to a catalog entry beyond last
                used entry or disk catalog is invalid.
        """
        self.get_sectors().hexdump(start, size, width, ellipsis, file=file)

    def get_digest(self, mode: int = None, algorithm: str = None) -> str:
        """Generate hexadecimal digest of file data.

        Available digest modes are:
            DIGEST_MODE_ALL (0) - Digest of file data and all attributes.
            DIGEST_MODE_FILE (2) - Digest of files data including
                load and execution addresses, but not access mode.
            DIGEST_MODE_DATA (3) - Digest of file data not including
                load and execution addresses or access mode.

        Args:
            mode: Optional; Digest mode. Default is DIGEST_MODE_FILE.
            algorithm: Optional; Algorithm to use instead of the default SHA1.
        Returns:
            Hexadecimal digest string.
        Raises:
            IndexError: The 'self' object points to a catalog entry beyond last
                used entry or disk catalog is invalid.
        """
        if algorithm is None:
            algorithm = 'sha1'
        if mode is None:
            mode = DIGEST_MODE_FILE
        data = self.readall()
        loadbytes = (self.load_address & 0x3FFFF).to_bytes(3, 'little')
        execbytes = (self.exec_address & 0x3FFFF).to_bytes(3, 'little')
        locked = self.locked
        if mode in (DIGEST_MODE_ALL, DIGEST_MODE_USED):
            data = b''.join((loadbytes, execbytes, bchr(locked), data))
        elif mode == DIGEST_MODE_FILE:
            data = b''.join((loadbytes, execbytes, data))
        return hashlib.new(algorithm, data,
                           usedforsecurity=False).hexdigest()  # type: ignore[call-arg]

    @property
    def sha1(self) -> str:
        """SHA1 digest of file data including load and execution addresses.

        If the 'self' object points to a catalog entry beyond last
            used entry, empty string is returned.
        """
        if self.index >= self.side.number_of_files:
            return ''
        return self.get_digest(DIGEST_MODE_FILE)

    @property
    def sha1data(self) -> str:
        """SHA1 digest of file data not including load and execution addresses.

        If the 'self' object points to a catalog entry beyond last
            used entry, empty string is returned.
        """
        if self.index >= self.side.number_of_files:
            return ''
        return self.get_digest(DIGEST_MODE_DATA)

    @property
    def sha1all(self) -> str:
        """SHA1 digest of file data including load and execution addresses and access mode.

        If the 'self' object points to a catalog entry beyond last
            used entry, empty string is returned.
        """
        if self.index >= self.side.number_of_files:
            return ''
        return self.get_digest(DIGEST_MODE_ALL)

    def clear(self) -> None:
        """Clear catalog entry."""
        self.side.modified = True
        self.entry1[:] = bytes(8)  # type: ignore
        self.entry2[:] = bytes(8)  # type: ignore

    def validate(self, warnall: bool = False) -> bool:
        """Validate catalog entry.

        Validate file name and start and end sectors. Issue a warning and return
        False if entry is not valid. Only first encountered problem is reported.

        Returns:
            A boolean indicating if entry is valid.
        """
        isvalid = True
        if any(not Entry.isnamechar(x) for x in self.entry1[0:7]):
            warn(ValidationWarning("Invalid file name in catalog entry #%d" %
                                   (self.index + 1)))
            # Invalid file names happen. Issue warning, but don't invalidate disk.
            # isvalid = False
        if (isvalid or warnall) and not Entry.isnamechar((self.entry1[7] & 127)):
            warn(ValidationWarning("Invalid directory name in catalog entry #%d" %
                                   (self.index + 1)))
            # Invalid file names happen. Issue warning, but don't invalidate disk.
            # isvalid = False
        if (isvalid or warnall) and (self.start_sector > self.side.number_of_sectors
                                     or self.start_sector < CATALOG_SECTORS):
            warn(ValidationWarning("Invalid start sector (%d) in catalog entry #%d" %
                                   (self.start_sector, self.index + 1)))
            isvalid = False
        if (isvalid or warnall) and (self.end_sector > self.side.number_of_sectors
                                     or self.end_sector < CATALOG_SECTORS
                                     or self.end_sector < self.start_sector):
            warn(ValidationWarning("Invalid end sector (%d) in catalog entry #%d" %
                                   (self.start_sector, self.index + 1)))
            isvalid = False
        return isvalid

    def get_high_bits(self, index: int) -> int:
        """Get bit field from high bits byte.

        High bits byte contains highest bits of file attributes. This method
        is used internally by property methods.

        Args:
            index: Bitfield index. Valid values are:
                0 - High bits of Start sector.
                1 - High bits of Load address.
                2 - High bits of File length.
                3 - High bits of Execution address.
        Returns:
            Value of the bitfield.
        """
        return (self.entry2[6] >> (2 * index)) & 3

    def set_high_bits(self, index: int, value: int) -> None:
        """Set bit field in high bits byte.

        This method is used internally by property methods.

        Args:
            index: Bitfield index. Valid values are:
                0 - High bits of Start sector.
                1 - High bits of Load address.
                2 - High bits of File length.
                3 - High bits of Execution address.
            value: New bitfield value.
        """
        mask = 3 << (2 * index)
        bits = (value & 3) << (2 * index)
        self.entry2[6] = (self.entry2[6] & ~mask) | bits  # type: ignore

    PROPERTY_NAMES = {
        "index": "File entry index.",
        "fullname": "Full file name including directory name.",
        "load_addr": "File load address.",
        "exec_addr": "File execution address.",
        "access": 'File access mode - L if file is locked, empty otherwise.',
        "size": "File length in bytes.",
        "start_sector": "Logical number of the first sector containing file data.",
        "end_sector": "Logical number of the first sector after file data.",
        "sectors": "Number of sectors occupied by file data",
        "sha1": "SHA1 digest of file data including load and execution addresses.",
        "sha1_data": "SHA1 digest of file data not including load and execution addresses.",
        "sha1_all": "SHA1 digest of file data including load "
                    "and execution addresses and access mode.",
        "image_path": "Full path of the floppy disk image file.",
        "image_filename": "File name of the floppy disk image file.",
        "image_basename": "File name of the floppy disk image file without extension.",
        "side": "Floppy disk side number - 1 or 2.",
        "directory": "File directory name.",
        "filename": "File name not including directory name.",
        "fullname_ascii": "Full file name without translation of ASCII code 0x60 "
                          "to unicode Pound sign.",
        "displayname": "File name as displayed by CAT",
        "locked": "File access mode - True if file is locked.",
        "dir_str": "Directory prefix as displayed by CAT command.",
        "drive": "Drive number according to DFS: 0 for side 1, 2 for side 2.",
        "head": "Head index: 0 for side 1, 1 for side 2.",
        }

    def get_properties(self, for_format: bool = False, level: int = 0) -> Dict[str, object]:
        """Get dictionary of all file properties.

        Args:
            for_format: Include additional redundant properties
                suitable for custom listing format, but not needed
                for dump.
        Returns:
            Dictionary of file properties.
        """
        access = "L" if self.locked else ""

        attrs = {
            'index': self.index + 1,
            'fullname': self.fullname,
            'load_addr': self.load_address,
            'exec_addr': self.exec_address,
            'access': access,      # "L" or ""
            'size': self.size,
            'start_sector': self.start_sector,
            'sectors': self.sectors_count,
            'sha1': LazyString(cast(Property[Entry, str],  # pylint: disable=no-member
                                    Entry.sha1).fget, self),
            'sha1_data': LazyString(cast(Property[Entry, str],  # pylint: disable=no-member
                                         Entry.sha1data).fget, self),
            'sha1_all': LazyString(cast(Property[Entry, str],  # pylint: disable=no-member
                                        Entry.sha1all).fget, self)
            }

        if level == 0:
            ids = {
                'image_path': self.side.image.path,
                'image_filename': self.side.image.filename,
                'image_basename': self.side.image.basename,
                'side': self.head + 1
            }
            attrs = {**ids, **attrs}

        if not for_format:
            attrs["load_addr"] = "%06X" % cast(int, attrs["load_addr"])
            attrs["exec_addr"] = "%06X" % cast(int, attrs["exec_addr"])
            attrs["size"] = "%06X" % cast(int, attrs["size"])
            attrs["sha1"] = str(attrs["sha1"])
            attrs["sha1_data"] = str(attrs["sha1_data"])
            attrs["sha1_all"] = str(attrs["sha1_all"])
            return attrs

        directory = self.directory
        dirstr = directory + '.' if directory != self.side.image.current_dir else ''
        redund_attrs = {
            'directory': directory,
            'filename': self.filename,
            'fullname_ascii': self.fullname_ascii,
            'displayname': self.displayname,
            'locked': self.locked,  # True or False
            'dir_str': dirstr,  # "D." or ""
            'drive': self.drive,  # First side is drive 0, second side is drive 2
            'head': self.head,
            'end_sector': self.end_sector
        }

        return {**attrs, **redund_attrs}

    def listing_entry(self, fmt=None) -> str:
        """Generate catalog listing entry line according to selected format.

        Predefined formats are:
            LIST_FORMAT_RAW (0)   - Raw text - only full name.
            LIST_FORMAT_INFO (1)  - As displayed by *INFO command.
            LIST_FORMAT_INF (2)   - As in .inf files.
            LIST_FORMAT_CAT (3)   - As displayed by *CAT command.
            LIST_FORMAT_JSON (4)  - JSON
            LIST_FORMAT_XML (5)   - XML
            LIST_FORMAT_TABLE (6) - Fixed-width text table.

        Args:
            fmt: Optional; Selected format. Value can be one of LIST_FORMAT_...
                constant or custom formatting string.
        """
        if fmt is None:
            fmt = LIST_FORMAT_INFO
        if fmt == LIST_FORMAT_TABLE:
            fmt = Entry.TABLE_FORMAT
        if not isinstance(fmt, str):
            if fmt == LIST_FORMAT_RAW:
                line = self.fullname
            elif fmt == LIST_FORMAT_INFO:
                access = "L" if self.locked else " "
                line = ('%-10s %1s  %06X %06X %06X %03X' %
                        (self.fullname, access, self.load_address,
                         self.exec_address, self.size, self.start_sector))
            elif fmt == LIST_FORMAT_INF:
                line = str(self.get_inf())
            elif fmt == LIST_FORMAT_CAT:
                directory = self.directory
                access = "L" if self.locked else " "
                dirstr = directory + '.' if directory != self.side.image.current_dir else ''
                line = ('%4s%-7s  %1s' % (dirstr, self.filename, access)).ljust(15)
            elif fmt == LIST_FORMAT_JSON:
                attrs = self.get_properties(for_format=False, level=0)
                line = json_dumps(attrs)
            elif fmt == LIST_FORMAT_XML:
                attrs = self.get_properties(for_format=False, level=0)
                line = xml_dumps(attrs, "file")
            else:
                raise ValueError("invalid listing format")

        else:
            attrs = self.get_properties(for_format=True, level=0)
            line = fmt.format_map(attrs)

        return line

    @property
    def info(self) -> str:
        """Info listing line."""
        return self.listing_entry(LIST_FORMAT_INFO)

    @property
    def inf(self) -> str:
        """Line for inf."""
        return str(self.get_inf())

    def get_inf(self) -> 'Inf':
        """Create Inf object for this file."""
        inf = Inf()
        inf.filename = self.fullname_ascii.lstrip()
        inf.load_addr = self.load_address
        inf.exec_addr = self.exec_address
        inf.size = self.size
        inf.locked = self.locked
        inf.drive = self.side.head * 2
        inf.is_valid = True
        return inf

    def __str__(self) -> str:
        """Convert to string by generating info line."""
        return self.info

    def __repr__(self) -> str:
        """Textual representation."""
        return "<Entry %s:%d.#%d:%s>" % (self.side.image.filename, self.side.head*2,
                                         self.index, self.info)

    def __lt__(self, other: 'Entry') -> bool:
        """Compare based on full file name with capital and lower letters grouped together."""
        if isinstance(other, Entry):
            return self.sorting_string < other.sorting_string
        return NotImplemented

    def _match(self, pattern: ParsedPattern,
               default_head: int = None) -> bool:

        # If drive is present in name, it must match this side
        if pattern.head is not None:
            if pattern.head != self.head:
                return False
        # If drive is not present in name, this side must be default
        elif default_head is not None:
            if default_head != self.head:
                return False

        # If directory is not empty, is must match this file
        directory = self.__get_directory(True)
        if pattern.dirname is not None:
            if pattern.dirname.match(directory) is None:
                return False

        # Otherwise this file must be in default directory
        else:
            if self.directory != unicode_to_bbc(self.side.image.current_dir):
                return False

        if pattern.filename.match(self.__get_filename(True)) is None:
            return False

        pattern.match_count += 1
        return True

    def match_parsed(self,
                     parsed_patterns: Optional[PatternList],
                     default_head: int = None) -> bool:
        """Test whether the entry matches any on the parsed pattern list."""
        if parsed_patterns is None:
            return default_head is None or default_head == self.head
        return sum(self._match(parsed, default_head)
                   for parsed in parsed_patterns.patterns) != 0

    def match(self, pattern: PatternUnion = None,
              default_head: int = None) -> bool:
        """Test whether the entry filename matches the 'pattern' string.

        Uses standard 'fnmatch' function. If the pattern doesn't contain
        directory name portion, root directory (i.e. '$.') is prepended
        to the pattern.

        Returns:
            True if file name matches pattern.
        """
        if pattern is None:
            return default_head is None or default_head == self.head

        return self.match_parsed(self.side.image.compile_pattern(pattern))

    @staticmethod
    def get_word(buffer: memoryview) -> int:
        """Read unsigned short integer value from two-bytes buffer with little-endian byte order."""
        return int.from_bytes(buffer, 'little')

    def delete(self, ignore_access=False):
        """Delete file.

        Args:
            ignore_access: Optional; Allow deleting locked files. Default is False.
        """
        # pylint: disable=protected-access
        self.side.check_valid()
        if self.locked and not ignore_access:
            raise PermissionError("file '%s' is locked" % self.fullname)
        self.get_sectors().clear()
        self.side._remove_entry(self.index)

    @staticmethod
    def set_word(buffer: memoryview, value: int) -> None:
        """Write unsigned short integer value to two-bytes buffer in little-endian byte order."""
        buffer[:] = value.to_bytes(2, 'little')  # type: ignore
