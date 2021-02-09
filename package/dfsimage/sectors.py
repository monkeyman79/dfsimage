"""This module provides 'Sectors' class."""
import itertools
import hashlib
import sys

from typing import Any, Iterator, List
from typing import Iterable, Sequence, Tuple, Union, Optional
from typing import Protocol
from typing import cast
from itertools import islice

from .conv import bbc_to_unicode
from .misc import bchr

class SectorsOwnerProtocol(Protocol):
    """Sectors owner protocol for static analyzer."""
    modified: bool

class Sectors:
    """Non-continuous chain of blocks in floppy disk image."""

    # Translate non-printable characters to dots
    __HEXDUMP_TRANSLATION = bytes(x if 32 <= x < 127 else ord(b'.') for x in range(0, 256))

    def __init__(self, image: SectorsOwnerProtocol,
                 chunks: Iterable[memoryview], size: int,
                 used_size: int = None) -> None:
        """Construct 'Sectors' object.

        Args:
            chunks: Iterable of memoryviews.
            size: Total number of bytes in all chunks. This is always
                multiple of sector size.
            used_size: Optional; Size of used data e.g. if sectors
                belong to a file.
        """
        self.image = image
        self.chunks: Tuple[memoryview, ...] = tuple(chunks)
        self.size = size
        self.used_size = used_size if used_size is not None else size

    @property
    def chain(self) -> Iterator[int]:
        """Create 'itertools.chain' object, joining all fragments into one iterable object.

        Returns:
            An 'itertools.chain' object constructed from all 'memoryview' fragments.
        """
        return itertools.chain.from_iterable(self.chunks)

    def extend(self, other: 'Sectors') -> None:
        """Extend sectors chain."""
        if self.image is not other.image:
            raise ValueError("cannot merge sectors from different images")
        if self.used_size != self.size:
            raise ValueError("cannot extend partially used sectors")
        self.chunks = self.chunks + other.chunks
        self.size += other.size
        self.used_size += other.used_size

    def fill(self, value: int) -> None:
        """Fill all sectors with a byte."""
        self.image.modified = True
        for chunk in self.chunks:
            chunk[:] = bchr(value) * len(chunk)

    def clear(self) -> None:
        """Clear all sectors by filling it with zeros."""
        self.fill(0)

    def readall(self) -> bytes:
        """Read all sectors' data.

        Returns:
            All sectors' data as 'bytes' object.
        """
        return bytes(islice(self.chain, self.used_size))

    def writeall(self, data: Union[bytes, Sequence[int], 'Sectors'], size: int = None) -> None:
        """Write all sectors' data.

        If size of data is smaller that chain size, remaining
        bytes are filled with zeros.

        Args:
            data: Bytes or iterable of integers to copy from.
            size: Optional; Maximum number of bytes to write.
        Raises:
            ValueError: Provided data in combination with size
                doesn't fit in sectors.
        """
        self.image.modified = True
        # Don't forget that all those casts are just for static analysis
        if hasattr(data, "__bytes__"):
            data = cast(bytes, cast(Any, data).__bytes__())
        data_seq: Optional[Sequence[int]] = None
        data_iter: Optional[Iterator[int]] = None
        if hasattr(data, "__getitem__"):
            data_seq = cast(Sequence[int], data)
        elif hasattr(data, "__iter__"):
            data_iter = cast(Iterator[int], iter(cast(Any, data)))
        else:
            raise TypeError("bad type for Sectors.writeall")
        end = False
        offset = 0
        # Iterate over memory chunks and write data in parts
        for chunk in self.chunks:
            chunk_len = len(chunk)
            chunk_offset = 0
            if not end:
                # Maximum size of data to write to this chunk
                if size is not None:
                    max_size = min(chunk_len, size)
                else:
                    max_size = chunk_len
                bts: Union[Sequence[int], bytes]
                # Create bytes either from iterator or range of bytes
                if data_iter is not None:
                    bts = bytes(islice(data_iter, max_size))
                elif data_seq is not None:
                    bts = data_seq[offset:offset+max_size]
                # Write data to chunk
                bts_len = len(bts)
                chunk[:bts_len] = bts  # type: ignore
                offset += bts_len
                if size is not None:
                    size -= bts_len
                # Short read indicates end of data
                if size == 0 or bts_len < max_size:
                    end = True
                    chunk_offset = bts_len
            if end:
                # After end of data - fill remaining with 0
                chunk[chunk_offset:chunk_len] = bytes(chunk_len - chunk_offset)
        if size != 0:
            if (data_iter is not None and len(bytes(islice(data_iter, size))) != 0
                    or data_seq is not None and len(data_seq) > offset):
                raise ValueError("data too long")

    def __bytes__(self) -> bytes:
        """Read all sectors data when conversion to bytes is requested."""
        return self.readall()

    def __len__(self) -> int:
        """Total size of all sectors in chain."""
        return self.size

    @staticmethod
    def __translate_ascii(bstr: bytes) -> str:
        return bbc_to_unicode(bstr.translate(Sectors.__HEXDUMP_TRANSLATION).decode("ascii"))

    @staticmethod
    def hexdump_buffer(data: bytes, start: int = None, size: int = None,
                       width: int = None, ellipsis: bool = None,
                       file=sys.stdout) -> None:
        """Hexdecimal dump.

        Args:
            data: Buffer to dump.
            start: Optional; Starting offset.
            size: Optional; Number of bytes to dump.
            width: Optional; Number of bytes per line.
            ellipsis: Optional; If ellipsis is True, repeating lines will be skipped.
            file: Output stream. Default is sys.stdout.
        """
        m_start = 0 if start is None else start
        if width is None:
            width = 16
        if ellipsis is None:
            ellipsis = True
        if size is None:
            m_size = len(data) - m_start
        else:
            m_size = min(size, len(data) - m_start)
        prevdata: bytes = b''
        skip = 0
        while m_size > 0:
            cnt = min(width, m_size)
            linedata = data[m_start:m_start+cnt]
            if ellipsis and linedata == prevdata and m_size > width:
                if skip == 0:
                    print('.' * 3, file=file)
                    skip = 1
            else:
                line = '%06X  %-*s  %-*s' % (m_start, 3*width-1, linedata.hex(' ', 1),
                                             width, Sectors.__translate_ascii(linedata))
                print(line, file=sys.stdout)
                skip = 0
                prevdata = linedata
            m_size -= cnt
            m_start += cnt

    def hexdump(self, start: int = None, size: int = None, width: int = None,
                ellipsis: bool = None, file=sys.stdout) -> None:
        """Hexdecimal dump of sectors data.

        See hexdump_buffer.
        """
        Sectors.hexdump_buffer(self.readall(), start, size, width, ellipsis, file=file)

    def get_digest(self, algorithm: str = None) -> str:
        """Generate hexadecimal digest of sectors' data.

        Args:
            algorithm: Optional; Algorithm to use instead of the default SHA1.
        Returns:
            Hexadecimal digest string.
        """
        if algorithm is None:
            algorithm = 'sha1'
        return hashlib.new(algorithm, self.readall(),
                           usedforsecurity=False).hexdigest()  # type: ignore[call-arg]

    @staticmethod
    def decode_hexdump(data: str) -> bytes:
        """Decode binary data from hexdump."""
        offset = 0
        hasaddr = None
        ellipsis = False
        lines = data.splitlines()
        lines_data: List[bytes] = []

        for line in lines:
            line = line.strip()

            if line == '...':
                if len(lines_data) == 0:
                    raise ValueError("ellipsis invalid at start of data")
                if not hasaddr:
                    raise ValueError("ellipsis invalid without address")
                ellipsis = True
                continue

            nonspaces = sum(1 for c in line if c != ' ')

            s_pos = line.find(' ')
            if s_pos < 2:
                raise ValueError("unexpected address format")

            if s_pos == 2:
                if hasaddr:
                    raise ValueError("inconsistent address format")
                hasaddr = False
            else:
                if hasaddr is not None and not hasaddr:
                    raise ValueError("inconsistent address format")
                hasaddr = True
                addr = int(line[:s_pos], 16)
                line = line[s_pos:].strip()
                if ellipsis:
                    lastline = lines_data[-1]
                    while offset < addr:
                        lines_data.append(lastline)
                        offset += len(lastline)
                    ellipsis = False
                if addr != offset:
                    raise ValueError("address mismatch")
                nonspaces -= s_pos

            linebytes = []
            while nonspaces != 0:
                s_pos = line.find(' ')
                if s_pos != 2 and (s_pos != -1 or len(line) != 2):
                    raise ValueError("invalid hex data")
                val = int(line[:2], 16)
                linebytes.append(val)
                line = line[2:].strip()
                if not hasaddr or val == 32:
                    nonspaces -= 2
                else:
                    nonspaces -= 3

            lines_data.append(bytes(linebytes))
            offset += len(linebytes)

        return b''.join(lines_data)
