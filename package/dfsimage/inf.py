"""Classes for .inf files"""

from typing import Optional, Dict
from typing import cast
import os

from .simplewarn import warn
from .misc import InfWarning

def foldfilecase(dirname: str, file: str) -> str:
    """Normalize the file name letter case the hard way for WSL."""
    path = os.path.join(dirname, file)
    l_file = file.lower()
    if l_file == file:
        return l_file
    test_path = os.path.join(dirname, l_file)
    try:
        if not os.path.samefile(path, test_path):
            # Case sensitive - cannot fold
            return file
    except OSError:
        # Case sensitive - cannot fold
        return file
    return l_file


def foldcase(path: str) -> str:
    """Normalize the absolute path letter case the hard way for WSL."""
    if path.lower() == path:
        return path
    head, tail = os.path.split(path)
    if tail != '':
        # Try converting tail to lowercase and see if it
        # refers to the same file
        tail = tail.lower()
        test_path = os.path.join(head, tail)
        if test_path != path:
            try:
                if not os.path.samefile(path, test_path):
                    # Case sensitive - cannot fold
                    return path
            except OSError:
                # Case sensitive - cannot fold
                return path
        # Try folding preceding part
        return os.path.join(foldcase(head), tail)

    # Root element, can we fold that too?
    head = head.lower()
    if head == path:
        return head
    try:
        if not os.path.samefile(path, test_path):
            # Case sensitive - cannot fold
            return path
    except OSError:
        # Case sensitive - cannot fold
        return path
    return head

def canonpath(path: str) -> str:
    """Get canonical file path.

    Get full path, fold case and check again for case insensitive
    path parts on WSL.
    """
    path = os.path.normcase(os.path.realpath(path))
    return foldcase(path)

class Inf:
    """Inf file contents."""
    def __init__(self):
        self.is_valid = False
        self.inf_path = cast(str, None)
        self.filename = cast(str, None)
        self.load_addr = cast(int, None)
        self.exec_addr: Optional[int] = None
        self.size: Optional[int] = None
        self.locked: Optional[bool] = None
        self.drive = None  # Internal information, not in file

    def to_string(self):
        """Data to string"""

        if not self.is_valid:
            return "invalid"

        parts = [f"{self.filename:<12} {self.load_addr:06X}"]
        if self.exec_addr is not None:
            parts.append(f"{self.exec_addr:06X}")
        if self.size is not None:
            parts.append(f"{self.size:06X}")
        if self.locked:
            parts.append("Locked")
        return " ".join(parts)

    def __str__(self):
        return self.to_string()

    @classmethod
    def from_string(cls, value: str, allow_spaces=True, no_throw=False) -> 'Inf':
        """Read inf data from string.

        Args:
            value: Line read from inf file.
            allow_spaces: Optional; Select algorithm for determining end of file name
                in the inf file string. Each method may fail (or give incorrect results)
                for some inf files due to ambiguity in the inf file format variants.
                Default is True.
            no_throw: Optional; Don't throw exception in case of invalid inf file format,
                instead return 'Inf" object with 'is_valid' property set to False.
        Raises:
            ValueError: invalid inf data and 'no_throw' is not True.
        """

        value = value.rstrip()

        order = ["load_addr", "exec_addr", "size", "access",
                 # ignored fields:
                 "m_date", "m_time", "c_date", "c_time", "user", "aux"]
        items: Dict[str, int] = {}

        try:
            if allow_spaces:
                # expect to find end of file name at position 11
                # if landed within load address, scan back for space
                name_end = value.rfind(' ', 0, 13)
                if name_end == -1:
                    name_end = value.find(' ')
            else:
                name_end = value.find(' ')

            # No space in inf file
            if name_end == -1:
                raise ValueError("invalid inf file")
            name = value[:name_end].rstrip()

            # Empty name - i.e. inf line starts with space
            if len(name) == 0:
                raise ValueError("invalid empty name")

            # If name starts with drive, strip it temporarily to check
            # for directory name
            drive = ''
            if name[0] == ':':
                if len(name) < 3 or name[1] < '0' and name[1] > '3' or name[2] != '.':
                    raise ValueError("invalid drive name: '%s'" % name[:3])
                drive = name[:3]
                name = name[3:]

            # If name doesn't start with directory name, insert '$.'
            if name[0] != '.' and (len(name) < 2 or name[1] != '.'):
                name = '$.%s' % name

            # Name without drive should be at most 9 characters
            if len(name) > 9:
                raise ValueError("name too long: '%s'" % name)
            name = drive + name

            # Split line after filename
            tail = value[name_end:].split()
            index = 0
            field = 0

            # Scan tail for hex values or special keywords
            while len(tail) > index:
                field_str = tail[index]

                # Ignore CRC=xxx
                if field_str.lower().startswith('crc='):
                    index += 1
                    field = -1
                    continue

                # Ignore BOOT=xxx
                if field_str.lower().startswith('boot='):
                    index += 1
                    field = -1
                    continue

                # Ignore NEXT <name>
                if field_str.lower() == 'next' and index + 1 < len(tail):
                    index += 2
                    field = -1
                    continue

                # Accept 'l' or 'locked', don't allow any hex fields following
                if field_str.lower() == 'l' or field_str.lower() == 'locked':
                    items["access"] = 0x19
                    index += 1
                    field = -1
                    continue

                # Hex field following special keyword is invalid
                if field == -1:
                    raise ValueError("unexpected inf field at #%d: '%s'" % (index, field_str))

                # More hex fields than expected
                if field >= len(order):
                    raise ValueError("too many inf fields at #%d: '%s'" % (index, field_str))

                # Assign consecutive hex fields
                field_name = order[field]
                try:
                    field_value = int(field_str, 16)
                except ValueError as err:
                    if len(err.args) > 0:
                        err.args = ("%s in inf field #%d (%s): '%s'" %
                                    (err.args[0], index, field_name, field_str), )
                    raise

                items[field_name] = field_value
                field += 1
                index += 1

            if "load_addr" not in items:
                raise ValueError("load address missing in inf file")

            inf = cls()
            inf.filename = name
            inf.load_addr = items.get("load_addr")
            inf.exec_addr = items.get("exec_addr")
            inf.size = items.get("size")
            access = items.get("access")
            if access is not None and access == 0x19:
                inf.locked = True
            inf.is_valid = True

            return inf

        except ValueError:
            if no_throw:
                return cls()
            raise

    def save(self, path: str = None) -> None:
        """Save inf data to file.

        Args:
            path: Optional; Path to inf file.
        Raises:
            ValueError: both 'path' and 'self.host_file' are None.
            ValueError: self.is_valid is False.
            OSError: writing to inf file failed.
        """
        if not self.is_valid:
            raise ValueError("writing invalid Inf object")
        if path is None:
            path = self.inf_path
            if path is None:
                raise ValueError("no file name for writing Inf object")
        data = "%s\n" % self.to_string()
        with open(path, "w") as inf_file:
            inf_file.write(data)

    @classmethod
    def load(cls, path: str, allow_spaces=True, no_throw=False) -> 'Inf':
        """Load inf data from file.

        Args:
            path: Path to inf file.
            allow_spaces: Optional; Select algorithm for determining end of file name
                in the inf file string. Each method may fail (or give incorrect results)
                for some inf files due to ambiguity in the inf file format variants.
                Default is True.
            no_throw: Optional; Don't throw exception in case of invalid inf file format,
                instead return 'Inf" object with 'is_valid' property set to False.
        Raises:
            ValueError: invalid inf data and 'no_throw' is not True.
            OSError: reading inf file failed
        """
        try:
            data: Optional[str] = None

            # Allow only one line of text, don't throw if followed some empty lines
            with open(path, "r") as inf_file:
                for line in inf_file:
                    if data is None:
                        data = line
                    elif len(line.strip()) != 0:
                        raise ValueError('excessive lines in inf file')

            if data is None:
                raise ValueError('empty inf file')

            # Read inf data from first line
            inf = cls.from_string(data, allow_spaces, no_throw)
            if inf.size is not None:
                file_size = os.path.getsize(path[:-4])
                if file_size != inf.size:
                    raise ValueError("file size in inf (%d) doesn't match actual size (%d)"
                                     % (inf.size, file_size))
            inf.inf_path = path

            return inf

        except (ValueError, OSError) as err:
            if no_throw:
                return cls()
            # Decorate exception message with inf file name
            if len(err.args) > 0:
                err.args = ('%s: %s' % (path, err.args[0]), )
            raise

class InfDirectoryCache:
    """Cache all inf files in a single directory."""

    def __init__(self, path: str) -> None:
        """Construct directory cache.

        Args:
            path: Directory full path. Must be already canonical.
        """
        self.inf_map: Dict[str, Inf] = {}
        self.host_file_map: Dict[str, Inf] = {}
        #self.dfs_file_map: Dict[str, Inf] = {}
        self.dir_path = path
        if os.path.exists(path):
            self.scandir()

    def scandir(self) -> None:
        """Scan all inf files in directory"""
        inf_map: Dict[str, Inf] = {}
        data_map: Dict[str, str] = {}

        # Iterate over all files in directory
        with os.scandir(self.dir_path) as f_iter:
            for entry in f_iter:
                # Skip files not ending with .inf
                if not entry.is_file() or not entry.name.lower().endswith(".inf"):
                    continue
                # Convert to lower case if possible
                name = foldfilecase(self.dir_path, entry.name)
                full_path = os.path.join(self.dir_path, name)
                # Skip inf file if there is no matchin data file
                if not os.path.exists(full_path[:-4]):
                    continue
                # Try to load the file, on exception issue warning and continue
                try:
                    inf = Inf.load(full_path, no_throw=False)
                    inf_map[name] = inf
                    data_map[name[:-4]] = name
                except (ValueError, OSError) as err:
                    if len(err.args) > 0:
                        warn(InfWarning(err.args[0]))
        # corner case:
        #  a, a.inf, a.inf.inf
        #  -> a is data, a.inf is data, a.inf.inf is inf

        # Iterate over collected inf files
        for inf_name, inf in inf_map.items():
            # Ignore .inf file if it has it's own .inf
            if inf_name not in data_map:
                # Map 'Inf' objects by inf file name
                self.inf_map[inf_name] = inf
                # Check for conflicting infs for the same DFS file
                #dfs_name = cast(str,inf.filename)
                #prev_inf = self.dfs_file_map.get(dfs_name)
                #if prev_inf is not None:
                #    prev_inf_name = os.path.basename(cast(str,prev_inf.inf_path))
                #    warn(InfWarning("conflicting inf files for dfs file %s "
                #                    "in directory %s: %s, %s" %
                #                    (dfs_name, self.dir_path, inf_name,
                #                     prev_inf_name)))
                # Map 'Inf' objects by dfs file name
                #self.dfs_file_map[dfs_name] = inf
        # Iterate over data files matched for infs
        for data_path, inf_name in data_map.items():
            # Ignore data file if inf has been 'cancelled'
            inf = cast(Inf, inf_map.get(inf_name))
            if inf is not None:
                self.host_file_map[data_path] = inf

    def update(self, inf_name: str, inf: Inf = None):
        """Update cache with new inf file.

        Args:
            inf_name: Basename of inf file. Must be already case-folded.
            inf: Optional; Inf object with data in the inf file.
        """
        # If inf data is not provided, load it from file
        if inf is None:
            try:
                inf_path = os.path.join(self.dir_path, inf_name)
                inf = Inf.load(inf_path, no_throw=False)
            except (ValueError, OSError) as err:
                if len(err.args) > 0:
                    warn(InfWarning(err.args[0]))
                return
        # Update all maps
        self.inf_map[inf_name] = inf
        self.host_file_map[inf_name[:-4]] = inf
        #dfs_name = cast(str,inf.filename)
        #self.dfs_file_map[dfs_name] = inf

    def get_by_host_file(self, host_file: str) -> Optional[Inf]:
        """Get Inf by host data file name.

        Args:
            host_file: Basename of host data file. Must be already case folded.
        Returns:
            Inf object if valid matching inf file exists, 'None' otherwise.
        """
        return self.host_file_map.get(host_file)

    def get_by_inf_file(self, inf_file: str) -> Optional[Inf]:
        """Get Inf by inf file name.

        Args:
            inf_file: Basename of inf file. Must be already case folded.
        Returns:
            Inf object if valid inf file exists, 'None' otherwise.
        """
        return self.inf_map.get(inf_file)

    #def get_by_dfs_file(self, dfs_name: str) -> Optional[Inf]:
    #    """Get Inf by DFS file name.
    #
    #    Args:
    #        dfs_name: Full DFS file name
    #    Returns:
    #        Inf object if valid matching inf file exists, 'None' otherwise.
    #    """
    #    return self.dfs_file_map.get(dfs_name)

class InfCache:
    """Cache inf files in all visited directories."""

    def __init__(self):
        self.directory_map: Dict[str, InfDirectoryCache] = {}

    def get_directory_cache(self, path: str) -> InfDirectoryCache:
        """Get or create per-direcotry cache.

        Args:
            path: absolute or relative directory path.
        Return:
            Per-directory cache object.
        """
        path = canonpath(path)
        cache = self.directory_map.get(path)
        if cache is not None:
            return cache
        cache = InfDirectoryCache(path)
        self.directory_map[path] = cache
        return cache

    def get_inf_by_host_file(self, host_file: str) -> Optional[Inf]:
        """Get Inf by host data file name.

        Args:
            host_file: Host data file - absolute or relative path.
        Returns:
            Inf object if valid matching inf file exists, 'None' otherwise.
        """
        path = canonpath(host_file)
        cache = self.get_directory_cache(os.path.dirname(path))
        return cache.get_by_host_file(os.path.basename(path))

    def get_inf_by_inf_file(self, inf_file: str) -> Optional[Inf]:
        """Get Inf by inf file name.

        Args:
            inf_file: Inf file - absolute or relative path.
        Returns:
            Inf object if valid matching inf file exists, 'None' otherwise.
        """
        path = canonpath(inf_file)
        cache = self.get_directory_cache(os.path.dirname(path))
        return cache.get_by_inf_file(os.path.basename(path))

    #def get_inf_by_dfs_file(self, dir_name: str, dfs_file: str) -> Optional[Inf]:
    #    """Find Inf in host direcotry by dfs file name.
    #
    #    Args:
    #        dir_name: Host directory - absolute or relative path.
    #        dfs_file: DFS file name.
    #    Returns:
    #        Inf object if valid matching inf file exists, 'None' otherwise.
    #    """
    #    path = canonpath(dir_name)
    #    cache = self.get_directory_cache(path)
    #    return cache.get_by_dfs_file(dfs_file)

    def update(self, inf_name: str, inf: Inf = None):
        """Update cache with new inf file.

        Args:
            inf_name: Inf file - absolute or relative path.
            inf: Optional; Inf object with data in the inf file.
        """
        path = canonpath(inf_name)
        cache = self.get_directory_cache(os.path.dirname(path))
        cache.update(os.path.basename(inf_name), inf)
