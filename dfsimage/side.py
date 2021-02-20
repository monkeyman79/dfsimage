"""This module provides class 'Side' which represents one side of floppy image."""

import sys
import hashlib

from typing import Optional, Generator, Sequence, Union, List
from typing import Dict, Iterable, IO, NamedTuple
from typing import cast

from . import simplewarn

from .simplewarn import warn

from .consts import CATALOG_SECTORS, CATALOG_SECTOR1, CATALOG_SECTOR2, SECTOR_SIZE
from .consts import SECTORS, MAX_FILES, SINGLE_SECTORS, DOUBLE_SECTORS

from .enums import DigestMode, ListFormat, WarnMode
from .enums import ListFormatUnion
from .misc import bchr, json_dumps, xml_dumps
from .misc import LazyString, ValidationWarning
from .conv import bbc_to_unicode, unicode_to_bbc, from_bcd, to_bcd

from .sectors import Sectors
from .pattern import PatternUnion
from .entry import Entry
from .protocol import ImageProtocol, Property


FoundFreeBlock = NamedTuple('FoundFreeBlock', [('sector_number', int),
                                               ('catalog_index', int)])


class Side:
    """Represents one side of a floppy image."""

    TABLE_FORMAT = (
        "{displayname:15}|{number_of_files:2}|"
        "{title:12}|{opt_str:4}|"
        "{sectors:3}|{last_used_sector:3}|{free_bytes:6}|"
        "{max_free_blk:6}|{sha1_files}"
        )

    def __init__(self, image: ImageProtocol, head: int) -> None:
        """Construct 'Side' object representing single floppy side in a disk image.

        Args:
            image (:class:`Image`): Floppy image object.
            head: Floppy disk side index - 0 or 1.
        """
        #: :class:`Image`: Parent Image object
        self.image = image
        #: int: Floppy disk side index - 0 or 1
        self.head = head % image.heads
        #: int: Number of sectors
        self.total_sectors = self.image.sectors_per_head
        self._csector1 = self._logical_sector(CATALOG_SECTOR1)
        self._csector2 = self._logical_sector(CATALOG_SECTOR2)
        self.isvalid = True

    @property
    def modified(self) -> bool:
        """Modified flag from parent Image object.

        :meta private:
        """
        return self.image.modified

    @modified.setter
    def modified(self, value: bool) -> None:
        self.image.modified = value

    def _sector(self, track: int, sector: int) -> memoryview:
        """See :meth:`Image._sector`."""
        # pylint: disable=protected-access
        return self.image._sector(self.head, track, sector)

    def _logical_sector(self, sector: int) -> memoryview:
        """See :meth:`Image._logical_sector`."""
        # pylint: disable=protected-access
        return self.image._logical_sector(self.head, sector)

    def _track(self, track: int) -> memoryview:
        """See :meth:`Image._track`."""
        # pylint: disable=protected-access
        return self.image._track(self.head, track)

    def get_sectors(self, start_track: int, start_sector: int, end_track: int, end_sector: int,
                    used_size: int = None) -> Sectors:
        """
        Get :class:`Sectors` object for sectors range.

        Return :class:`Sectors` object referencing possibly non-continuous area in
        image data, corresponding to a sequence of sectors. The area covers sectors
        in range from the start sector to the end sector exclusively, i.e.
        `end_track` and `end_sector` should point to first sector after the range.
        For `end_track` and `end_sector`, value pairs (80, 0) and (79, 10)
        (or (40, 0) and (39, 10) for 40 track disks) are both valid and point to
        the same end-of-disk-side sector.

        Args:
            start_track: Start track number - 0 to 79.
            start_sector: Start sector number on track - 0 to 9.
            end_track: End track number - 0 to 80.
            end_sector: End sector number on track - 0 to 10.
            used_size: Size in bytes of data contained in sectors sequence
                especially last sector can be only partially utilized.
        Raises:
            IndexError: Invalid head, track or sector number.
            IndexError: Trying to access sectors other than catalog sectors and
                Image is open for catalog access only.
            ValueError: The :class:`Image` object has been closed.
            ValueError: The start sector is after the end sector.
        """
        return self.image.get_sectors(self.head, start_track, start_sector,
                                      end_track, end_sector, used_size)

    def get_logical_sectors(self, start_logical_sector: int, end_logical_sector: int,
                            used_size: int = None) -> Sectors:
        """
        Get :class:`Sectors` object for sectors range by logical sector numbers.

        Args:
            start_logical_sector: Start sector logical number on track - 0 to 799.
            end_logical_sector: End sector number on track - 0 to 800.
            used_size: Size in bytes of data contained in sectors sequence
                especially last sector can be only partially utilized.
        Raises:
            IndexError: Invalid sector number
            IndexError: Trying to access sectors other than catalog sectors and
                Image is open for catalog access only.
            ValueError: The :class:`Image` object has been closed.
            ValueError: The start sector is after the end sector.
        """
        return self.image.get_logical_sectors(self.head, start_logical_sector, end_logical_sector,
                                              used_size)

    def get_all_sectors(self) -> Sectors:
        """Get :class:`Sectors` object for entire disk side sectors range."""
        return self.get_sectors(0, 0, self.image.tracks, 0)

    @property
    def drive(self) -> int:
        """int: Drive number according to DFS.

        0 for side 1, 2 for side 2
        """
        return self.head * 2

    @property
    def title(self) -> str:
        """str: Floppy title.

        Floppy title is up to 12 characters.

        Raises:
            ValueError: Assigned title is longer than 12 chars
        """
        vbytes = bytes((x & 127 for x in bytes(self._csector1[0:8])+bytes(self._csector2[0:4])))
        return bbc_to_unicode(vbytes.decode("ascii").rstrip(chr(0)))

    @title.setter
    def title(self, value: str) -> None:
        if len(value) > 12:
            raise ValueError("title too long")
        vbytes = unicode_to_bbc(value).ljust(12, chr(0)).encode("ascii")
        self.modified = True
        self._csector1[0:8] = vbytes[0:8]  # type: ignore
        self._csector2[0:4] = vbytes[8:12]  # type: ignore
        if self.image._mmb_entry is not None:
            self.image._mmb_entry.title = value

    @property
    def sequence_number(self) -> int:
        """int: Sequence number.

        Sequence number is a Binary Coded Decimal value incremented by the Disk Filing System
        each time the disk catalog is modified.
        """
        return from_bcd(self._csector2[4])

    @sequence_number.setter
    def sequence_number(self, value: int) -> None:
        self.modified = True
        self._csector2[4] = to_bcd(value)  # type: ignore

    @property
    def last_entry_offset(self) -> int:
        """int: Last entry offset.

        The offset to the last file entry in both catalog sectors. This number divided by 8
        gives a number of files on the floppy. This number must a multiple of 8 or floppy
        image is invalid.

        Raises:
            ValueError: Assigned value is outside of valid range of is not a multiple of 8.
        """
        return self._csector2[5]

    @last_entry_offset.setter
    def last_entry_offset(self, value: int) -> None:
        if value & 7 != 0 or value > 248 or value < 0:
            raise ValueError("invalid end of catalog offset value")
        self.modified = True
        self._csector2[5] = value  # type: ignore

    @property
    def number_of_files(self) -> int:
        """int: Number of files in catalog.

        Number of files is calculated based on the last entry offset value.

        Raises:
            ValueError: Assigned value is less than 0 or greater than maximum value of 31.
        """
        # If disk side is isvalid it may contain garbage in catalog.
        # To hide this garbage and prevent modifications, return 0 as number of files.
        if not self.isvalid:
            return 0
        return self.last_entry_offset // 8

    @number_of_files.setter
    def number_of_files(self, value: int) -> None:
        if value < 0:
            raise ValueError("invalid number of files value")
        if value > MAX_FILES:
            raise ValueError("catalog full")
        self.last_entry_offset = value * 8

    @property
    def opt_byte(self) -> int:
        """int: Options byte.

        The options byte contains Boot option flag and highest bits of 'Number of sectors' value.
        If bits 2,3,6 or 7 are not all zero, floppy image is considered invalid or unsupported.
        """
        return self._csector2[6]

    @opt_byte.setter
    def opt_byte(self, value: int) -> None:
        self.modified = True
        self._csector2[6] = value  # type: ignore

    @property
    def opt(self) -> int:
        """int: Boot option flag.

        Action to be taken when the disc is booted. Valid values are:

          * 0 - off:  No action.
          * 1 - LOAD: Execute `*LOAD $.!BOOT` command.
          * 2 - RUN:  Execute `*RUN $.!BOOT` command.
          * 3 - EXEC: Execute `*EXEC $.!BOOT` command.

        Raises:
            ValueError: Assigned value is not in valid range.
        """
        return (self.opt_byte >> 4) & 3

    @opt.setter
    def opt(self, value: int) -> None:
        if value < 0 or value > 3:
            raise ValueError("invalid boot option value")
        self.opt_byte = (self.opt_byte & 0xcf) | ((value & 3) << 4)

    @property
    def opt_str(self) -> str:
        """str: Boot option string.

        Raises:
            ValueError: Assigned value is not in boot option string.
        """
        return Side.boot_opt_to_str(self.opt)

    @opt_str.setter
    def opt_str(self, value) -> None:
        self.opt = Side.str_to_boot_opt(value)

    @property
    def number_of_sectors(self) -> int:
        """int: Total number of sectors on disk side.

        This value should be either 800 for 80 track disks, or 400 for 40 track disks.
        """
        return self._csector2[7] + ((self._csector2[6] & 3) << 8)

    @number_of_sectors.setter
    def number_of_sectors(self, value: int) -> None:
        if value not in (SINGLE_SECTORS, DOUBLE_SECTORS):
            raise ValueError("invalid total number of sectors")
        self.modified = True
        self._csector2[7] = value & 255  # type: ignore
        self._csector2[6] = (self._csector2[6] & ~3) | ((value >> 8) & 3)  # type: ignore

    @property
    def used_sectors(self) -> int:
        """int: Number of sectors occupied by files and catalog."""
        if not self.isvalid:
            return self.number_of_sectors
        result = CATALOG_SECTORS
        for file in self.files:
            result += file.sectors_count
        return result

    @property
    def free_sectors(self) -> int:
        """int: Number of free sectors."""
        return self.number_of_sectors - self.used_sectors

    @property
    def free_bytes(self) -> int:
        """int: Number of free bytes on the floppy disk side."""
        return self.free_sectors * SECTOR_SIZE

    @property
    def last_used_sector(self) -> int:
        """int: Index of first sector after last sector occupied by any file.

        This method is used for calculating minimum disk image file size.
        If image validation failed, this method returns number of physical
        sectors to prevent any data loss.
        """
        if not self.image.isvalid:
            return self.total_sectors
        if self.number_of_files == 0:
            return CATALOG_SECTORS
        # If image is valid then first file is the located last on floppy
        return self.get_entry(0).end_sector

    @property
    def largest_free_block(self) -> int:
        """int: Size of largest continuous free block."""
        if not self.isvalid:
            return 0
        largest = 0
        end = self.number_of_sectors
        for file in self.files:
            largest = max(largest, end - file.end_sector)
            end = file.start_sector
        largest = max(largest, end - CATALOG_SECTORS)
        return largest * SECTOR_SIZE

    def _find_free_block(self, min_size: int) -> Optional[FoundFreeBlock]:
        """Find first free block of required size.

        Args:
            min_size: Minimum block size in byte.
        Returns:
            Logical sector number of start of free block and
            index for catalog entry insertion.
        """
        sectors = (min_size + SECTOR_SIZE - 1) // SECTOR_SIZE
        start = CATALOG_SECTORS
        index = self.number_of_files - 1
        while index >= 0:
            file = self.get_entry(index)
            gap = file.start_sector - start
            if gap < 0:
                raise RuntimeError("bad file order in disk catalog")
            if gap >= sectors:
                return FoundFreeBlock(start, file.index + 1)
            start = file.end_sector
            index -= 1
        gap = self.number_of_sectors - start
        if gap < 0:
            raise RuntimeError("bad file order in disk catalog")
        if gap >= sectors:
            return FoundFreeBlock(start, 0)
        return None

    def _remove_entry(self, index: int) -> None:
        end = self.last_entry_offset + 8
        start = (index + 2) * 8

        self.modified = True
        if start != end:
            self._csector1[start-8:end-8] = self._csector1[start:end]
            self._csector2[start-8:end-8] = self._csector2[start:end]

        self[self.number_of_files-1]._clear()
        self.last_entry_offset = end - 16

    def _insert_entry(self, index: int, fullname: str,
                      start_sector: int, size: int) -> 'Entry':
        end = self.last_entry_offset + 8
        start = (index + 1) * 8
        sectors = (size + SECTOR_SIZE - 1) // SECTOR_SIZE

        if index < self.number_of_files:
            if start_sector < self[index].end_sector:
                raise ValueError("sector overlaps previous file (%d < %d)"
                                 % (start_sector, self[index].end_sector))
        if start_sector < 2:
            raise ValueError("sector overlaps catalog (%d < 2)"
                             % start_sector)

        if index > 0:
            if start_sector + sectors > self[index-1].start_sector:
                raise ValueError("sector overlaps next file (%d > %d)"
                                 % (start_sector + sectors, self[index-1].start_sector))
        if start_sector + sectors > self.number_of_sectors:
            raise ValueError("sector overflows disk (%d > %d)"
                             % (start_sector + sectors, self.number_of_sectors))

        if end + 8 > SECTOR_SIZE:
            raise ValueError("catalog sector overflow (%d)" % (end + 8))

        self.modified = True
        if start != end:
            self._csector1[start+8:end+8] = self._csector1[start:end]
            self._csector2[start+8:end+8] = self._csector2[start:end]

        self.last_entry_offset = end

        entry = self[index]
        entry._clear()
        entry.fullname = fullname
        entry.start_sector = start_sector
        entry.size = size
        return entry

    def _add_entry(self, fullname: str, data: bytes, *, load_addr: Optional[int],
                   exec_addr: Optional[int], locked: bool,
                   replace: bool, ignore_access: bool, no_compact: bool) -> Entry:
        self._check_valid()
        size = len(data)

        entry = self.find_entry(fullname)
        if entry is not None:
            if not replace:
                raise FileExistsError("file '%s' already exists" % entry.fullname)
            entry.delete(ignore_access)
            entry = None

        if self.number_of_files == MAX_FILES:
            raise RuntimeError("catalog full")
        if size > self.free_sectors * SECTOR_SIZE:
            raise RuntimeError("no space for file in floppy image")

        if size > self.largest_free_block and not no_compact:
            self.compact()
        found = self._find_free_block(size)
        if found is None:
            raise RuntimeError("no continuous free block for file")
        if load_addr is None:
            load_addr = 0
        if exec_addr is None:
            exec_addr = load_addr
        entry = self._insert_entry(found.catalog_index, fullname,
                                   found.sector_number, size)
        entry.writeall(data)
        entry.load_address = load_addr
        entry.exec_address = exec_addr
        entry.locked = locked
        return entry

    def _check_valid(self) -> None:
        """Check if catalog is valid before modifications."""
        if not self.isvalid:
            raise IOError("disk image is corrupted, can't be modified")

    def can_add_file(self, size: int, no_compact: bool) -> bool:
        """Check if side can accommodate new file of given size.

        Args:
            size: File size.
            no_compact: If `True` check if there is a continuous free block
                big enough for the new file without compacting the disk.
        """
        if not self.isvalid or self.number_of_files == MAX_FILES:
            return False
        if self.largest_free_block >= size:
            return True
        if not no_compact and self.free_sectors * SECTOR_SIZE >= size:
            return True
        return False

    def _to_fullname(self, filename: str) -> str:
        """Prepend current directory name ($) if not present in filename.

        Filename is not a pattern - characters *?![] are not special and
        are all valid filename characters.
        """

        filename, head = self.image._to_fullname(filename, self.head)

        if head != self.head:
            raise ValueError("bad drive")

        return filename

    def find_entry(self, filename: str) -> Optional['Entry']:
        """Find entry by filename.

        Args:
            filename: File name.
        Return:
            Found :class:`Entry` or None.
        Raises:
            ValueError: File name is invalid.
        """
        i = 0
        name = unicode_to_bbc(self._to_fullname(filename))
        while i < self.number_of_files:
            start = (i+1) * 8
            end = (i+2) * 8
            entry = Entry(self, i, self._csector1[start:end], self._csector2[start:end])
            if entry.fullname_ascii.lower() == name.lower():
                return entry
            i += 1
        return None

    def compact(self) -> None:
        """Compact fragmented free space on disk.

        Raises:
            IOError: Disk validation failed.
        """
        self._check_valid()
        start_sector = 2
        last_used_sector = self.last_used_sector
        entries = list(self.files)
        entries.reverse()
        for entry in entries:
            if entry.start_sector != start_sector:
                data = self.get_logical_sectors(entry.start_sector, entry.end_sector)
                end_sector = start_sector + entry.sectors_count
                self.get_logical_sectors(start_sector, end_sector).writeall(data)
                entry.start_sector = start_sector
            start_sector += entry.sectors_count
        if start_sector != last_used_sector:
            self.get_logical_sectors(start_sector, last_used_sector).clear()

    def get_entry(self, index: Union[int, str]) -> 'Entry':
        """Get file entry by index or name.

        Args:
            index: File entry index in range 0 - 30, or file name
        Returns:
            An :class:`Entry` object.
        Raises:
            IndexError: Index is out of valid range.
            KeyError: File name not found.
            TypeError: Index is neither `str` nor `int`.
        """
        if isinstance(index, int):
            if index < 0 or index > 30:
                raise IndexError("invalid file entry index")
            start = (index+1) * 8
            end = (index+2) * 8
            return Entry(self, index, self._csector1[start:end], self._csector2[start:end])

        if isinstance(index, str):
            entry = self.find_entry(index)
            if entry is None:
                raise KeyError("file not found")
            return entry

        raise TypeError("index must be str or int, not %s" % type(index).__name__)

    @property
    def files(self) -> Generator[Entry, None, None]:
        """Generator[:class:`Entry`, None, None]: Sequence of file entries."""
        index = 0
        while index < self.number_of_files:
            yield self.get_entry(index)
            index += 1

    def get_files(self, pattern: PatternUnion = None,
                  silent: bool = False) -> List[Entry]:
        """Get list of file entries matching pattern.

        Args:
            pattern (Optional[:class:`PatternUnion`]): Pattern or list of patterns.
                See :meth:`Entry.match`.
            silent: Don't raise exception if pattern doesn't match any file.
        Raises:
            ValueError: The `pattern` argument is invalid.
            FileNotFoundError: No file found matching `pattern`.
        """
        if pattern is None:
            return list(self.files)

        parsed = self.image._compile_pattern(pattern)
        files = [file for file in iter(self.files)
                 if file._match_parsed(parsed, self.head)]
        if not silent:
            parsed.ensure_matched()
        return files

    def __iter__(self) -> Generator[Entry, None, None]:
        return self.files

    def __getitem__(self, index: Union[int, str]) -> Entry:
        return self.get_entry(index)

    def __len__(self) -> int:
        return self.number_of_files

    def __str__(self) -> str:
        return "Side(%s, %d)" % (self.image, self.head)

    def __repr__(self) -> str:
        """Textual representation."""
        return self.__str__()

    def validate(self, warn_mode: WarnMode = None) -> bool:
        """Validate catalog.

        Validate disk image. If an error is encountered, issue a warning and
        mark disk side as invalid, preventing disk modifications.

        Args:
            warn_mode (Optional[WarnMode]): Warning mode.
                Default is :data:`WarnMode.FIRST`.
        Returns:
            A boolean indicating if catalog is valid.
        """
        if warn_mode is None:
            warn_mode = WarnMode.FIRST
        isvalid = True
        warnall = warn_mode == WarnMode.ALL

        # pylint: disable=unused-argument
        def formatmsg(message: Union[Warning, str]) -> str:
            return ("%s: %s: %s"
                    % (type(message).__name__, self.image_displayname, str(message)))

        if warn_mode == WarnMode.NONE:
            simplewarn.mute(ValidationWarning)

        simplewarn.current_format = formatmsg
        try:

            if ((isvalid or warnall)
                    and self.number_of_sectors != DOUBLE_SECTORS
                    and self.number_of_sectors != SINGLE_SECTORS):
                isvalid = False
                warn(ValidationWarning("Invalid total number of sectors (%d)"
                                       % self.number_of_sectors))
            if (isvalid or warnall) and self.number_of_sectors > self.total_sectors:
                isvalid = False
                warn(ValidationWarning("Number of sectors in directory (%d) greater than "
                                       "the number of physical sectors (%d)"
                                       % (self.number_of_sectors, self.total_sectors)))
            if (isvalid or warnall) and self.last_entry_offset & 7 != 0:
                isvalid = False
                warn(ValidationWarning("Invalid end of catalog value (0x%02x)"
                                       % self.last_entry_offset))
            if (isvalid or warnall) and self.opt_byte & 0xcc != 0:
                isvalid = False
                warn(ValidationWarning("Invalid option byte or unsupported format (0x%02x)"
                                       % self.opt_byte))
            index = 0
            end_sector = self.number_of_sectors
            nfiles = self.number_of_files
            badorder = False
            while (isvalid or warnall) and index < nfiles:
                entry = self.get_entry(index)
                isvalid &= entry.validate(warnall)
                if (isvalid or warnall) and entry.end_sector > end_sector:
                    # Files are either overlapping or at least not ordered properly
                    warn(ValidationWarning("Catalog entries are not ordered properly in entry #%s"
                                           % index))
                    badorder = True
                    isvalid = False
                end_sector = entry.start_sector
                index += 1
            if badorder:
                self._check_sectors_allocation(warnall)

        finally:
            simplewarn.current_format = simplewarn.formatmsg
            simplewarn.unmute(ValidationWarning)

        return isvalid

    @property
    def image_displayname(self) -> str:
        """str: File name of the floppy disk image with **MMB** index
           or double sided disk head index appended."""
        return ("%s:%d" % (self.image.filename, self.head) if self.image.heads > 1
                else self.image.displayname)

    #: Disk side properties available as keywords for listing header format strings.
    #:
    #: :meta hide-value:
    PROPERTY_NAMES = {
        "side": "Floppy disk side number - 1 or 2.",
        "title": "Floppy title string.",
        "sequence": "Sequence number incremented by the Acorn DFS each time "
                    "the disk catalog is modified.",
        "opt_str": "Boot option string - one of 'off', 'LOAD', 'RUN', 'EXEC'.",
        "is_valid": "Disk validation result.",
        "number_of_files": "Number of files on the floppy disk side.",
        "sectors": "Number of sectors on disk reported by the catalog.",
        "free_sectors": "Number of free sectors.",
        "free_bytes": "Number of free bytes.",
        "used_sectors": "Number of used sectors",
        "max_free_blk_sectors": "Number of sectors in largest continuous free block.",
        "max_free_blk": "Size of largest continuous free block in bytes.",
        "sha1": "SHA1 digest of the entire floppy disk side surface.",
        "sha1_files": "SHA1 digest of all files on the floppy disk side including "
                      "their names and attributes.",
        "sha1_used": "SHA1 digest of floppy disk side surface excluding unused areas.",
        "path": "Full path of the floppy disk image file.",
        "filename": "File name of the floppy disk image file.",
        "basename": "File name of the floppy disk image file without extension.",
        "index": "Index of the disk image in the MMB file.",
        "displayname": "File name of the floppy disk image with MMB index "
                       "or double sided disk head number appended.",
        "index_or_head": "Disk image index for MMB file or "
                         "head number (0 or 1) for double sided disk.",
        "tracks": "Number of tracks on the floppy disk side.",
        "drive": "Drive number according to DFS: 0 for side 1, 2 for side 2.",
        "head": "Head index: 0 for side 1, 1 for side 2.",
        "end_offset": "Last entry offset byte in catalog sector. Indicates number of files "
                      "on the floppy disk image side.",
        "opt_byte": "Options byte in catalog sectors. Contains among other boot option value.",
        "opt": "Boot options value.",
        "last_used_sector": "Last used sector on floppy disk side.",
        "current_dir": "Current directory - '$' by default.",
        "locked": "Image locked flag in the MMB catalog - True if image is locked.",
        "initialized": "Image initialized flag in the MMB catalog - True if "
                       "image is initialized.",
        "mmb_status": "Image status in the MMB catalog - "
                      "'L' if image is locked, 'U' if image is uninitialized, "
                      "'I' if status flag is invalid, empty string otherwise.",
        "mmb_status_byte": "Raw MMB status byte value in the MMB catalog."
        }

    def get_properties(self, for_format: bool = False, recurse: bool = False,
                       level: int = 0,
                       pattern: PatternUnion = None,
                       sort=False, silent=False) -> Union[List, Dict[str, object]]:
        """Generate a dictionary of all floppy side properties.

        Args:
            for_format: Include additional redundant properties
                suitable for custom listing format, but not needed
                for dump.
            recurse: Include list of files with their properties.
            level: If level is 0, image file name is included
                in properties dictionary. If level is -1,
                skip disk side properties and instead
                return list of files with their properties.
            pattern (Optional[:class:`PatternUnion`]): Pattern for files included in the
                recursive list.
            sort (bool): Sort files by name.
            silent (bool): Don't raise exception if a pattern doesn't match any file.
        Returns:
            Dictionary of floppy disk side properties or list of files properties.
        Raise:
            ValueError: Pattern is invalid.
        """
        # pylint: disable=no-member
        if level >= 0:
            pre_attrs: Dict = {}
            if level == 0:
                pre_attrs['path'] = self.image.path
                pre_attrs['filename'] = self.image.filename
                if for_format:
                    pre_attrs['basename'] = self.image.basename

            if for_format or not self.image.is_mmb:
                pre_attrs['side'] = self.head + 1
            if for_format or self.image.is_mmb:
                pre_attrs['index'] = self.image.index

            attrs = {
                **pre_attrs,
                'title': self.title,
                'sequence': self.sequence_number,
                'opt_str': self.opt_str,
                'is_valid': self.isvalid,
                'number_of_files': self.number_of_files,
                'sectors': self.number_of_sectors,
                'free_sectors': self.free_sectors,
                'max_free_blk_sectors': self.largest_free_block // SECTOR_SIZE,
                'sha1': LazyString(cast(Property['Side', str], Side.sha1).fget, self),
                'sha1_files': LazyString(cast(Property['Side', str], Side.sha1files).fget, self),
                'sha1_used': LazyString(cast(Property['Side', str], Side.sha1used).fget, self)
                }
            if for_format or self.image.is_mmb:
                mmb_stat = self.image._mmb_status_byte
                attrs["locked"] = self.image.locked
                attrs["initialized"] = self.image.initialized
                attrs["mmb_status_bytes"] = mmb_stat
                attrs["mmb_status"] = self.image.MMB_STATUS_MAP.get(mmb_stat, 'I')
        # pylint: enable=no-member

        if for_format and level >= 0:
            attrs['displayname'] = self.image_displayname
            attrs['index_or_head'] = self.image.index if self.image.is_mmb else self.head

        if recurse or level < 0:
            file_list = [file.get_properties(for_format=False, level=level+1)
                         for file in self.get_files(pattern, silent)]
            if sort:
                file_list.sort()

            if level < 0:
                return file_list
            attrs["files"] = file_list

        if not for_format:
            attrs["sha1"] = str(attrs["sha1"])
            attrs["sha1_files"] = str(attrs["sha1_files"])
            attrs["sha1_used"] = str(attrs["sha1_used"])
            return attrs

        redund_attrs = {
            'tracks': self.number_of_sectors // SECTORS,
            'drive': self.head * 2,  # First side is drive 0, second side is drive 2
            'head': self.head,
            'end_offset': self.last_entry_offset,  # = (files-1)*8
            'opt_byte': self.opt_byte,
            'opt': self.opt,  # 0, 1, 2 or 3
            'used_sectors': self.used_sectors,
            'free_bytes': self.free_bytes,
            'max_free_blk': self.largest_free_block,
            'last_used_sector': self.last_used_sector,
            'current_dir': self.image.current_dir
        }

        return {**attrs, **redund_attrs}

    def dcat_line(self):
        """Generate index entry as displayed by ``*DCAT`` command.

        :meta private:
        """
        index = self.image.index if self.image.is_mmb else self.head
        if self.image.is_mmb:
            mmb_stat = self.image._mmb_status_byte
            status = self.image.MMB_STATUS_MAP.get(mmb_stat, 'I')
        else:
            status = ''
        return "%5d %12s %1s" % (index, self.title, status)

    def listing_header(self, fmt: ListFormatUnion = None,
                       file: IO = None) -> None:
        """Print catalog listing header lines according to selected format.

        See Side.PROPERTY_NAMES for list of available keys.

        Args:
            fmt (Optional[:class:`ListFormatUnion`]): Listing format.
                Value can be one of :class:`ListFormat` enum
                or custom formatting string. Nothing is printed
                if fmt in any ListFormat enum constant other than
                :data:`ListFormat.CAT`, :data:`ListFormat.DCAT` and
                :data:`ListFormat.TABLE`.
                If fmt is a string, the header is generated with `str.format` function.
            file: Output stream. Default is sys.stdout.
        Raises:
            ValueError: Parameter `fmt` is invalid.
        """
        if file is None:
            file = sys.stdout
        if fmt is None:
            fmt = ListFormat.CAT
        if fmt == ListFormat.TABLE:
            fmt = Side.TABLE_FORMAT
        drive = self.head * 2
        optstr = Side.boot_opt_to_str(self.opt)
        if fmt == '':
            pass
        elif isinstance(fmt, str):
            attrs = self.get_properties(for_format=True, recurse=False, level=0)
            print(fmt.format_map(cast(Dict[str, object], attrs)), file=file)
        elif fmt == ListFormat.DCAT:
            print(self.dcat_line(), file=file)
        elif fmt == ListFormat.CAT:
            print(f'{self.title} ({self.sequence_number:02})', file=file)
            print("%-20s%s" % (f'Drive {drive}', f'Option {self.opt} ({optstr})'), file=file)
            print("%-20s%s" % (f'Dir. :{drive}.{self.image.current_dir}', 'Lib. :0.$'), file=file)
            print("", file=file)
        elif fmt not in (ListFormat.RAW, ListFormat.INFO, ListFormat.INF,
                         ListFormat.JSON, ListFormat.XML):
            raise ValueError("invalid listing format")

    @staticmethod
    def _print_cat_lines(entries: Iterable[Entry], file, gap):
        """Print catalog lines, two files per line."""

        fname1 = None
        for entry in entries:
            if gap:
                print('', file=file)
                gap = False
            fname = entry.listing_entry(ListFormat.CAT)
            if fname1 is not None:
                print('%-20s%s' % (fname1, fname), file=file)
                fname1 = None
            else:
                fname1 = fname
        if fname1 is not None:
            print(fname1, file=file)
            fname1 = None

    def listing(self, fmt: ListFormatUnion = None,
                pattern: PatternUnion = None,
                header_fmt: ListFormatUnion = None, footer_fmt: ListFormatUnion = None,
                sort: bool = None, silent: bool = False, file: IO = None) -> None:
        """Print catalog listing.

        Print catalog listing using predefined format or custom
        formatting strings.

        For list of keys available for custom side header formatting string see
        :data:`Side.PROPERTY_NAMES`.

        For list of keys available for custom file entry formatting string see
        :data:`Entry.PROPERTY_NAMES`.

        Args:
            fmt (Optional[:class:`ListFormatUnion`]): Listing format. Value can
                be one of :class:`ListFormat` enum or a custom formatting string.
            pattern (Optional[:class:`PatternUnion`]): List only files matching
                pattern (see :meth:`Entry.match`).
            header_fmt (Optional[:class:`ListFormatUnion`]): Listing header format.
                Value can be one of :class:`ListFormat` enum or a custom
                formatting string.
                Default is no header, unless ``fmt`` is one of
                :data:`ListFormat.CAT`, :data:`ListFormat.DCAT` or
                :data:`ListFormat.TABLE`.
            footer_fmt (Optional[:class:`ListFormatUnion`]): Formatting
                string for listing footer.
                Default is no footer.
            sort (Optional[bool]): If this flag is ``True``, displayed files are
                sorted alphabetically, using the same algorithm as DFS uses,
                grouping upper and lower case of the same letter together.
                It is enabled by default for :data:`ListFormat.CAT` format
                and disabled for all other formats.
            silent (bool): Don't raise exception if a pattern doesn't
                match any file
            file: Output stream. Default is sys.stdout.
        Raises:
            ValueError: Format parameter is invalid.
            ValueError: Pattern is invalid.
            FileNotFoundError: No file found matching `pattern`.
        """
        if file is None:
            file = sys.stdout

        fmt = ListFormat.CAT if fmt is None else fmt

        header_fmt = fmt if header_fmt is None and not isinstance(fmt, str) else header_fmt

        if header_fmt is not None and header_fmt != '':
            self.listing_header(header_fmt, file=file)

        sort = (fmt == ListFormat.CAT) if sort is None else sort

        entries = self.get_files(pattern, silent)
        if sort:
            entries.sort()

        if fmt == ListFormat.CAT:
            self._print_cat_lines((e for e in entries
                                   if e.directory == self.image.current_dir),
                                  file, False)
            self._print_cat_lines((e for e in entries
                                   if e.directory != self.image.current_dir),
                                  file, True)

        elif fmt == ListFormat.JSON:
            attrs = self.get_properties(for_format=False, recurse=True,
                                        level=0, pattern=pattern)
            print(json_dumps(attrs), file=file, end='')

        elif fmt == ListFormat.XML:
            attrs = self.get_properties(for_format=False, recurse=True,
                                        level=0, pattern=pattern)
            print(xml_dumps(attrs, "side"), file=file)

        elif (fmt in (ListFormat.RAW, ListFormat.INFO, ListFormat.INF, ListFormat.TABLE)
              or isinstance(fmt, str) and fmt != ''):
            for entry in entries:
                print(entry.listing_entry(fmt), file=file)

        elif fmt != '' and fmt != ListFormat.DCAT:
            raise ValueError("invalid listing format")

        if footer_fmt is not None and footer_fmt != '':
            self.listing_header(footer_fmt, file=file)

    def cat(self, pattern: PatternUnion = None, silent: bool = False, file: IO = None) -> None:
        """See :meth:`Image.cat`.

        Args:
            pattern (Optional[:class:`PatternUnion`]): List only files matching
                pattern (see :meth:`Entry.match`).
            silent (bool): Don't raise exception if a pattern doesn't
                match any file
            file: Output stream. Default is sys.stdout.
        """
        self.listing(ListFormat.CAT, pattern, silent=silent, file=file)

    def info(self, pattern: PatternUnion = None, silent: bool = False, file: IO = None) -> None:
        """See :meth:`Image.info`.

        Args:
            pattern (Optional[:class:`PatternUnion`]): List only files matching
                pattern (see :meth:`Entry.match`).
            silent (bool): Don't raise exception if a pattern doesn't
                match any file
            file: Output stream. Default is sys.stdout.
        """
        self.listing(ListFormat.INFO, pattern, silent=silent, file=file)

    @staticmethod
    def boot_opt_to_str(boot_opt: int) -> str:
        """Convert Boot option flag to string as displayed by DFS.

        :meta private:

        Args:
            boot_opt: Boot option numerical value.
        Returns:
            Boot option string - one of 'off', 'LOAD', 'RUN', 'EXEC'.
        """
        if (boot_opt < 0) or (boot_opt > 3):
            raise ValueError("invalid boot option value")
        return ["off", "LOAD", "RUN", "EXEC"][boot_opt]

    @staticmethod
    def str_to_boot_opt(opt_str: str) -> int:
        """Convert Boot option string to flag value.

        :meta private:

        Args:
            opt_str: Boot option string - one of 'off', 'LOAD', 'RUN', 'EXEC'
                or valid number.
        Returns:
            Boot option flag value.
        Raise:
            ValueError: invalid boot option string
        """
        try:
            return ["off", "load", "run", "exec"].index(opt_str.lower())
        except ValueError:
            pass
        try:
            val = int(opt_str)
            if 0 <= val <= 3:
                return val
        except ValueError:
            pass
        raise ValueError("invalid boot option")

    def hexdump(self, start: int = None, size: int = None, width: int = None,
                ellipsis: bool = None, file: IO = None) -> None:
        """Hexdecimal dump of all sectors on this floppy side.

        Args:
            start: Starting offset.
            size: Number of bytes to dump.
            width: Number of bytes per line.
            ellipsis: Skip repeating lines.
            file: Output stream. Default is sys.stdout.
        """
        self.get_all_sectors().hexdump(start, size, width, ellipsis, file=file)

    def _check_sectors_allocation(self, warnall: bool = False) -> bool:
        """Check for overlapping sectors.

        Returns:
            Validation result. False if files overlap.
        """
        def warn_if(cond: bool, warning):
            if cond:
                warn(warning)

        invalid = False
        sectors_map = bytearray(bchr(0) * self.number_of_sectors)
        sectors_map[CATALOG_SECTOR1] = 254
        sectors_map[CATALOG_SECTOR2] = 254
        for file in self.files:
            if file.end_sector > self.number_of_sectors or file.end_sector < 0:
                warn_if(not invalid or warnall,
                        ValidationWarning("File #%d sector number invalid" % (file.index + 1)))
                invalid = True
                continue

            if file.start_sector > self.number_of_sectors or file.start_sector < 0:
                warn_if(not invalid or warnall,
                        ValidationWarning("File #%d sector number invalid" % (file.index + 1)))
                invalid = True
                continue

            for logical_sector in range(file.start_sector, file.end_sector):
                if sectors_map[logical_sector] == 254:
                    warn_if(not invalid or warnall,
                            ValidationWarning("File #%d overlaps catalog sectors"
                                              % (file.index + 1)))
                    invalid = True
                    continue

                if sectors_map[logical_sector] != 0:
                    warn_if(not invalid or warnall,
                            ValidationWarning("File #%d overlaps file #%d"
                                              % (file.index + 1, sectors_map[logical_sector])))
                    invalid = True
                    continue

                sectors_map[logical_sector] = file.index + 1

        return not invalid

    def format(self, tracks: int = None) -> None:
        """Initialize disk.

        Initialize disk by clearing directory sectors and writing in total number of sectors value
        in catalog.

        Args:
            tracks: Number of tracks - 80 or 40. Default is :data:`Image.tracks`
        """
        if tracks is None:
            tracks = self.image.tracks
        self.get_all_sectors().fill(0xe5)
        empty = bytes(SECTOR_SIZE)
        self._csector1[:] = empty  # type: ignore
        self._csector2[:] = empty  # type: ignore
        self.number_of_sectors = tracks * SECTORS

    def readall(self) -> bytes:
        """Read raw floppy side sectors data and return `bytes` object."""
        return self.get_all_sectors().readall()

    def writeall(self, data: Union[bytes, Sequence[int], Sectors]) -> None:
        """Write all side sectors data.

        Args:
            data: A `bytes` object or sequence of `int`.
        """
        self.get_all_sectors().writeall(data)

    def _used_data(self) -> bytes:
        """Read used floppy side areas in form suitable for digest."""
        # Start with catalog sector length to make it provably unique.
        cend = self.last_entry_offset
        parts = [b''.join((bchr(cend), self._csector1[:cend+8],
                           self._csector2[:cend+8]))]
        for file in self.files:
            parts.append(file.readall())
        return b''.join(parts)

    def _files_data(self) -> bytes:
        """Concatenate all files sorted alphabetically in form suitable for digest."""
        parts = []
        files = list(self.files)
        files.sort()
        for file in files:
            fullname = file.rawname
            loadaddr = (file.load_address & 0x3ffff).to_bytes(3, 'little')
            execaddr = (file.exec_address & 0x3ffff).to_bytes(3, 'little')
            length = file.size.to_bytes(3, 'little')
            parts.append(b''.join((fullname, loadaddr, execaddr, length, file.readall())))
        return b''.join(parts)

    def get_digest(self, mode: DigestMode = None, algorithm: str = None) -> str:
        """Generate hexadecimal digest of floppy side contents.

        Args:
            mode (Optional[DigestMode]): Selects digest mode.
                Default is :data:`DigestMode.ALL`.
            algorithm: Algorithm to use instead of the default 'SHA1'.
        Returns:
            Hexadecimal digest string.
        """
        if algorithm is None:
            algorithm = 'sha1'
        if mode is None:
            mode = DigestMode.ALL
        if mode == DigestMode.ALL:
            data = self.get_all_sectors().readall()
        elif mode == DigestMode.USED:
            data = self._used_data()
        else:
            data = self._files_data()
        return hashlib.new(algorithm, data,
                           usedforsecurity=False).hexdigest()  # type: ignore[call-arg]

    @property
    def sha1(self) -> str:
        """str: SHA1 digest of the entire floppy disk side surface."""
        return self.get_digest(DigestMode.ALL)

    @property
    def sha1files(self) -> str:
        """str: SHA1 digest of all files on the floppy disk side."""
        return self.get_digest(DigestMode.FILE)

    @property
    def sha1used(self) -> str:
        """str: SHA1 digest of floppy disk side surface excluding unused areas."""
        return self.get_digest(DigestMode.USED)
