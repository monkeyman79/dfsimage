"""This module contains MMBFile class."""

import os

from io import SEEK_SET

from typing import Generator, Optional, IO, Union, List, Dict
from typing import cast

from .consts import MMB_INDEX_SIZE, MMB_INDEX_ENTRY_SIZE, MMB_MAX_ENTRIES, MMB_SIZE
from .consts import MMB_STATUS_UNINITIALIZED

from .enums import ListFormat, ListFormatUnion
from .enums import WarnMode, OpenMode

from .misc import is_mmb_file

from .pattern import PatternUnion
from .mmbentry import MMBEntry
from .image import Image


class MMBOnbootList:
    """Indexable access to images inserted into drives at boot time."""

    def __init__(self, mmb_file: 'MMBFile'):
        self.mmb_file = mmb_file

    def __getitem__(self, index: int):
        return self.mmb_file.get_onboot(index)

    def __setitem__(self, index: int, value: int):
        self.mmb_file.set_onboot(index, value)

    def __len__(self):
        return 4


class MMBAllEntries:
    """Indexable access to all images, including uninitialized ones."""

    def __init__(self, mmb_file: 'MMBFile'):
        self.mmb_file = mmb_file

    def __iter__(self) -> Generator['MMBEntry', None, None]:
        """Sequence of all entries, including uninitialized ones."""
        index = 0
        while index < self.mmb_file.count:
            yield self.mmb_file.get_entry(index)
            index += 1

    def __getitem__(self, index: int) -> 'MMBEntry':
        return self.mmb_file.get_entry(index)

    def __len__(self) -> int:
        return self.mmb_file.count


class MMBFile:
    """Represents an open MMB file."""

    def __init__(self, filename: str, for_write: bool = False,
                 create: bool = False):
        """Open MMB file and construct MMBFile object.

        Args:
            filename: The MMB file name.
            for_write: Optional; Open image for write.
            create: Optional; Create new MMB file. Fail if file already exists.
        Raises:
            FileNotFoundError: File not found and 'create' is False.
            FileExistsError: File already exists and 'create' is True.
        """

        self._onboot_modified = False

        if not create:
            #: int: Maximum number of images in the **MMB** file
            self.count = is_mmb_file(filename)
        else:
            self.count = MMB_MAX_ENTRIES

        if self.count == 0:
            raise ValueError("%s: not a valid MMB file" % filename)

        self._dataview: Optional[memoryview] = memoryview(bytearray(MMB_INDEX_SIZE))
        self._entry_modified = bytearray(MMB_MAX_ENTRIES)
        #: str: Full path to the **MMB** file.
        self.path = os.path.abspath(filename)
        #: str: Name of the **MMB** file.
        self.filename = os.path.basename(filename)
        #: IO: File IO object.
        self.file: Optional[IO[bytes]] = None
        #: bool: File is open for read only
        self.is_read_only = not for_write
        #: bool: File is newly created
        self.is_new_file = create
        #: int: Reference count. This includes all active :class:`Image` objects
        #: open from this **MMB**.
        self.refcnt = 1

        filemode = "xb" if create else "rb+" if for_write else "rb"
        try:
            self.file = open(filename, filemode)
            if not self.is_new_file:
                if self.file.readinto(  # type: ignore[attr-defined]
                        self._dataview) != MMB_INDEX_SIZE:
                    raise RuntimeError("%s: unexpected MMB file short read"
                                       % filename)
            else:
                for entry in self.all_entries:
                    entry.status_byte = MMB_STATUS_UNINITIALIZED
                for index in range(4):
                    self.set_onboot(index, index)
                self.file.truncate(MMB_SIZE)
                self.save()

        except:  # noqa: E722
            self.close(False)
            raise

    @classmethod
    def open(cls, filename: str, for_write: bool = False) -> 'MMBFile':
        """Open an **MMB** file.

        The :class:`MMBFile` object created by this function keeps an open file handle to
        the MMB file, so make sure to call the :meth:`close()` method when your
        program is done with the created object, or use the ``'with'`` statement.

        Args:
            filename: The **MMB** file name.
            for_write (bool): Open the file for write.
        Raises:
            FileNotFoundError: File not found.
        Returns:
            A new :class:`MMBFile` object.
        """
        return cls(filename, for_write=for_write)

    @classmethod
    def create(cls, filename: str):
        """Create a new **MMB** file.

        The :class:`MMBFile` object created by this function keeps an open file handle to
        the **MMB** file, so make sure to call the :meth:`close()` method when your
        program is done with the created object, or use the ``'with'`` statement.

        Args:
            filename: The **MMB** file name.
        Raises:
            FileExistsError: File already exists.
        Returns:
            A new :class:`MMBFile` object.
        """
        return cls(filename, for_write=True, create=True)

    def _close(self, save: bool):
        if self.file is not None:
            if not self.is_read_only and self.modified and save:
                self.save()
            self.file.close()
            self.file = None
            self._dataview = None

    def _not_closed(self):
        if self._dataview is None:
            raise ValueError('%s: MMB file is closed' % self.filename)

    def close(self, save: bool = True):
        """Decrement reference count, close and invalidate object when no longer
        referenced.

        Args:
            save: Write the catalog data back to the **MMB** file if it is
                not open for read only, and data has been modified.
        """
        if self.refcnt == 0:
            raise RuntimeError("already closed")
        self.refcnt -= 1
        if not save:
            if self.file is not None:
                self._close(False)
                if self.is_new_file:
                    os.remove(self.path)

        elif self.refcnt == 0:
            self._close(True)

    def save(self):
        """Save the **MMB** file catalog."""
        self.file.seek(0, SEEK_SET)
        if self.file.write(self._dataview) != MMB_INDEX_SIZE:
            raise IOError("%s: failed to write index" % self.filename)
        self.clear_modified()

    @property
    def modified(self):
        """The **MMB** file catalog has been modified since last save."""
        return self._onboot_modified or any(b != 0 for b in self._entry_modified)

    def is_entry_modified(self, index: int) -> bool:
        """Get catalog entry modified flag.

        Args:
            index: Image index
        Returns:
            Modified flag value
        """
        return self._entry_modified[index] != 0

    def set_entry_modified(self, index: int, value: bool):
        """Set catalog entry modified flag.

        Args:
            index: Image index
            value: New modified flag value
        """
        if value:
            if self.is_read_only:
                raise PermissionError("%s: file is open for read only"
                                      % self.filename)
        self._entry_modified[index] = value

    def clear_modified(self):
        """Clear all modified flags after catalog has been saved."""
        self._entry_modified.clear()
        self._onboot_modified = False

    def incref(self) -> IO[bytes]:
        """Increment reference count and return IO object."""
        self.refcnt += 1
        if self.file is None:
            raise RuntimeError("MMB file is not open")
        return self.file

    def get_onboot(self, drive: int) -> int:
        """Get index of image inserted into drive at boot time.

        Args:
            drive: Emulated drive number
        """
        self._not_closed()
        if drive < 0 or drive > 3:
            raise IndexError("index out of range")
        dataview = cast(memoryview, self._dataview)
        return dataview[drive] | (dataview[drive + 4] << 8)

    def set_onboot(self, drive: int, image: int):
        """Set index of image inserted into drive at boot time.

        Args:
            drive: Emulated drive number
            image: Disk image index
        """
        self._not_closed()
        if drive < 0 or drive > 3:
            raise IndexError("index out of range")
        if image < 0 or image > 510:
            raise ValueError("invalid image index")
        if self.is_read_only:
            raise PermissionError("%s: file is open for read only"
                                  % self.filename)
        dataview = cast(memoryview, self._dataview)
        dataview[drive] = image & 0xFF  # type: ignore
        dataview[drive + 4] = image >> 8  # type: ignore
        self._onboot_modified = True

    def get_entry(self, index: int) -> MMBEntry:
        """Get n-th image entry.

        Args:
            index: Image index.
        Return:
            An :class:`MMBEntry` object referencing the image.
        """
        self._not_closed()
        offset = (index + 1) * MMB_INDEX_ENTRY_SIZE
        dataview = cast(memoryview, self._dataview)
        return MMBEntry(index=index,
                        dataview=dataview[offset:offset + MMB_INDEX_ENTRY_SIZE],
                        owner=self)

    @property
    def all_entries(self) -> MMBAllEntries:
        """:class:`MMBAllEntries`: Sequence of all disk image entries."""
        return MMBAllEntries(self)

    @property
    def entries(self) -> Generator[MMBEntry, None, None]:
        """Generator[:class:`MMBEntry`, None, None]: Sequence of initialized disk image entries."""
        index = 0
        while index < self.count:
            entry = self.get_entry(index)
            if entry.initialized:
                yield entry
            index += 1

    @property
    def onboot(self) -> MMBOnbootList:
        """MMBOnbootList: List of images inserted into drives at boot time."""
        return MMBOnbootList(self)

    def open_entry(self, entry: Union[int, MMBEntry], open_mode: OpenMode = None,
                   warn_mode: WarnMode = None,
                   catalog_only=False) -> 'Image':
        """Open contained disk image.

        Args:
            entry (Union[int, :class:`MMBEntry`]): An :class:`MMBEntry` object
                or image index.
            open_mode (:class:`OpenMode`): File open mode.
            warn_mode: Warning mode for validation.
                Default is :data:`WarnMode.FIRST`.
            catalog_only (bool): Open image only for reading catalog.
        Returns:
            An :class:`Image` object
        """
        if not isinstance(entry, MMBEntry):
            entry = self.get_entry(entry)
        return Image.open(self.filename, for_write=not self.is_read_only and not catalog_only,
                          open_mode=open_mode, warn_mode=warn_mode, index=entry,
                          catalog_only=catalog_only)

    def drecat(self, warn_mode: WarnMode = None) -> int:
        """Rebuild catalog of disk titles.

        Args:
            warn_mode: Warning mode for validation.
                Default is :data:`WarnMode.FIRST`.
        Returns:
            Number of titles that have changed.
        """
        count = 0
        for entry in self.entries:
            with entry.open(warn_mode=warn_mode, catalog_only=True) as image:
                if entry.title != image.title:
                    entry.title = image.title
                    count += 1
        return count

    #: **MMB** file properties returned by :meth:`get_properties` method.
    #:
    #: :meta hide-value:
    PROPERTY_NAMES = {
        "path": "Full path of the MMB file.",
        "filename": "File name of the MMB file.",
        "image_count": "Number of images in the MMB file."
    }

    @property
    def image_count(self) -> int:
        """int: Number of initialized images in the **MMB** file."""
        return sum(True for entry in self.entries)

    def get_properties(self, for_format: bool, recurse: bool,  # pylint: disable=unused-argument
                       level: int = 0,
                       pattern: PatternUnion = None,
                       sort=False, silent=False,  # pylint: disable=unused-argument
                       start_index: int = None,
                       end_index: int = None) -> Union[List, Dict[str, object]]:
        """Get dictionary of all **MMB** file properties.

        Args:
            for_format: Ignored.
            recurse: Include a list of images and recursively a list
                of files with their properties in the property dictionary.
            level: If level is -1 skip **MMB** file properties and
                instead return list of images with their properties. If level
                is -2, return list of files with their properties.
            pattern (Optional[:class:`PatternUnion`]): Pattern for files included in the
                recursive list.
            sort (bool): Sort files by name.
            silent (bool): Don't raise exception if a pattern doesn't match any file.
            start_index: Start of the disk images range to include in the list.
            end_index: End of the disk images range to include in the list.
        Returns:
            Dictionary of **MMB** file properties or list of image or file properties.
        """
        if level >= 0:
            attrs = {
                'path': self.path,
                'filename': self.filename,
                'image_count': self.image_count
                }

        if recurse or level < 0:
            image_list = []
            parsed = None
            for entry in self.all_entries:
                if start_index is not None and entry.index < start_index:
                    continue
                if end_index is not None and entry.index >= end_index:
                    continue
                if not entry.initialized and (start_index is None or end_index is None
                                              or end_index != start_index + 1):
                    continue
                with entry.open(warn_mode=WarnMode.NONE, catalog_only=False) as image:
                    if parsed is None:
                        parsed = image.compile_pattern(pattern)
                    image_list.append(
                        image.get_side(0).get_properties(
                            for_format=False, recurse=recurse, level=level+1,
                            pattern=parsed, sort=sort, silent=True))
            if not silent and parsed is not None:
                parsed.ensure_matched()

            if level == -2:
                return [file for file_list in image_list for file in file_list]

            if level < 0:
                return image_list

            attrs["sides"] = image_list

        return attrs

    def listing(self, fmt: ListFormatUnion = None,
                pattern: PatternUnion = None,
                start_index: int = None, end_index: int = None,
                silent=False,
                **kwargs) -> None:
        """List all or range of images in the **MMC** file.

        See :meth:`Image.listing`

        Args:
            fmt (Optional[:class:`ListFormatUnion`]): Listing format. Value can
                be one of :class:`ListFormat` enum or a custom formatting string.
            pattern (Optional[:class:`PatternUnion`]): List only files matching
                pattern (see :meth:`Entry.match`).
            start_index: Starting image index for partial listing
            end_index: Ending image index for partial listing
            silent: Don't raise exception if a pattern doesn't
                match any file
            kwargs: Remaining arguments are passed to the :meth:`Image.listing`
                method.
        """
        count = 0
        line = ""
        parsed = None
        for entry in self.all_entries:
            if start_index is not None and entry.index < start_index:
                continue
            if end_index is not None and entry.index >= end_index:
                continue
            if not entry.initialized and (start_index is None or end_index is None
                                          or end_index != start_index + 1):
                continue
            with entry.open(warn_mode=WarnMode.NONE, catalog_only=True) as image:
                if pattern is not None and parsed is None:
                    parsed = image.compile_pattern(pattern)
                if fmt == ListFormat.DCAT:
                    line += image.sides[0].dcat_line()
                    count += 1
                    if count == 4:
                        print(line)
                        line = ""
                        count = 0
                else:
                    image.listing(fmt=fmt, pattern=parsed, silent=True, **kwargs)
        if count != 0:
            print(line)
        if not silent and parsed is not None:
            parsed.ensure_matched()

    def __str__(self) -> str:
        """Get string representation of MMBFile."""
        if self.file is None:
            return "MMBFile('%s') [closed]" % self.filename
        return "MMBFile('%s', for_write=%s)" % (self.filename, not self.is_read_only)

    def __repr__(self) -> str:
        """Textual representation."""
        return self.__str__()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(exc_type is None)
        return False
