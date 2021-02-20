"""This module contains MMBEntry class."""

from typing import Protocol, IO, Union

from .consts import MMB_INDEX_ENTRY_SIZE
from .consts import MMB_STATUS_OFFSET, MMB_STATUS_LOCKED, MMB_STATUS_UNLOCKED
from .consts import MMB_STATUS_UNINITIALIZED, MMB_STATUS_UNINITIALIZED_MASK

from .enums import OpenMode, WarnMode

from .misc import MMBWarning
from .simplewarn import warn
from .conv import bbc_to_unicode, unicode_to_bbc


class MMBFileProtocol(Protocol):
    """Protocol for MMBFile class."""

    filename: str
    count: int

    # pylint: disable=missing-function-docstring

    def is_entry_modified(self, index: int) -> bool:
        ...

    def set_entry_modified(self, index: int, value: bool):
        ...

    def incref(self) -> IO[bytes]:
        ...

    def close(self, save: bool = True):
        ...

    def open_entry(self, entry: Union[int, 'MMBEntry'], open_mode: OpenMode = None,
                   warn_mode: WarnMode = None, catalog_only=False):
        ...

    @property
    def is_read_only(self) -> bool:
        ...

    # pylint: enable=missing-function-docstring


class MMBEntry:
    """Represents entry in the **MMB** file catalog."""

    def __init__(self, index: int, dataview: memoryview = None,
                 owner: MMBFileProtocol = None):
        self._modified = False
        #: int: Image index
        self.index = index
        self._offset = (index + 1) * MMB_INDEX_ENTRY_SIZE
        self._dataview = (memoryview(bytearray(MMB_INDEX_ENTRY_SIZE))
                          if dataview is None else dataview)
        #: :class:`MMBFile`: The :class:`MMBFile` object.
        self.owner = owner

    def open(self, open_mode: OpenMode = None, warn_mode: WarnMode = None,
             catalog_only=False):
        """Open disk from **MMB** catalog entry.

        Args:
            open_mode (Optional[OpenMode]): File open mode.
                Default is :data:`OpenMode.ALWAYS`.
            warn_mode (Optional[WarnMode]):
                Warning mode for validation.
            catalog_only (bool): Open image only for reading catalog data.
        Returns:
            An :class:`Image` object
        """
        if self.owner is None:
            raise ValueError("no 'MMBFile' object")
        return self.owner.open_entry(self, open_mode, warn_mode, catalog_only)

    @property
    def modified(self) -> bool:
        """**MMB** catalog entry modified."""
        if self.owner is not None:
            return self.owner.is_entry_modified(self.index)
        return self._modified

    @modified.setter
    def modified(self, value: bool):
        if self.owner is not None:
            self.owner.set_entry_modified(self.index, value)
        else:
            self._modified = value

    @property
    def status_byte(self) -> int:
        """Disk status byte in **MMB** catalog, no questions asked.

        :meta private:
        """
        return self._dataview[MMB_STATUS_OFFSET]  # type: ignore

    @status_byte.setter
    def status_byte(self, value: int):
        if self._dataview[MMB_STATUS_OFFSET] != value:  # type: ignore
            self._modified = True
            self._dataview[MMB_STATUS_OFFSET] = value  # type: ignore

    @property
    def locked(self) -> bool:
        """Disk locked flag in the **MMB** catalog."""
        return self.status_byte == MMB_STATUS_LOCKED

    @locked.setter
    def locked(self, value: bool):
        if not self.initialized:
            raise PermissionError("image is not initialized")

        if value:
            # Lock image
            self.status_byte = MMB_STATUS_LOCKED
        else:
            # Unlock image
            self.status_byte = MMB_STATUS_UNLOCKED

    @property
    def initialized(self) -> bool:
        """Disk initialized flag in the **MMB** catalog."""
        return self.status_byte & MMB_STATUS_UNINITIALIZED_MASK != MMB_STATUS_UNINITIALIZED

    @initialized.setter
    def initialized(self, value: bool):
        if value:
            if not self.initialized:
                # Activate image
                self.status_byte = MMB_STATUS_UNLOCKED
        else:
            # Deactivate image
            if self.locked:
                raise PermissionError("image is locked")
            self.status_byte = MMB_STATUS_UNINITIALIZED

    def dkill(self) -> bool:
        """Set disk status in **MMB** catalog to uninitialized."""

        # Deactivate disk in the MMB index
        if not self.initialized:
            warn(MMBWarning("image already uninitialized"))
            return False

        self.initialized = False
        return True

    def drestore(self) -> bool:
        """Set disk status in **MMB** catalog to initialized."""

        # Activate disk in the MMB index
        if self.initialized:
            warn(MMBWarning("image already initialized"))
            return False

        self.initialized = True
        return True

    @property
    def title(self) -> str:
        """Disk title string in **MMB** catalog."""
        vbytes = bytes(self._dataview[0:12])
        return bbc_to_unicode(vbytes.decode("ascii").rstrip(chr(0)))

    @title.setter
    def title(self, value: str) -> None:
        if len(value) > 12:
            raise ValueError("title too long")
        vbytes = unicode_to_bbc(value).ljust(12, chr(0)).encode("ascii")
        if vbytes != self._dataview[0:12]:
            self.modified = True
            self._dataview[0:12] = vbytes  # type: ignore

    def __str__(self):
        """String representation."""
        return "%5i %12s %1s" % (self.index, self.title,
                                 "U" if not self.initialized
                                 else "P" if self.locked
                                 else " ")

    def __repr__(self):
        """Textual representation."""
        return "MMBEntry %s %s" % (self.owner.filename if self.owner is not None else "",
                                   str(self))
