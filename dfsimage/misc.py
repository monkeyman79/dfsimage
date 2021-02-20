"""Miscellaneous utility classes and function used by the package."""

import os
import json
import xml.etree.ElementTree as ET
import hashlib

from typing import Sequence, Optional, Union, TypeVar, List, Callable

from .consts import MMB_INDEX_SIZE, MMB_SIZE, MMB_DISK_SIZE
from .consts import MMB_MAX_ENTRIES


class DFSWarning(UserWarning):
    """DFS operation warning."""


class MMBWarning(UserWarning):
    """MMB operation warning."""


class ValidationWarning(UserWarning):
    """Warning caused by invalid data in disk catalog."""


class InfWarning(UserWarning):
    """Warning caused by invalid data in inf file or conflicting files."""


# pylint: disable=invalid-name
bchr = tuple([bytes((x, )) for x in range(0, 256)]).__getitem__


def rjoin(sep: Optional[str], array: Sequence[str]) -> Union[str, List[str]]:
    """Concatenate string with additional separator at the end.

    Return a string which is the concatenation of the strings in iterable.
    The 'sep' string is used as separator between elements of array and
    is appended to the end of result, unless the array is empty. The 'sep'
    argument can be 'None' is which case original array is returned.
    """
    if sep is not None:
        if len(array) == 0:
            return ''
        return sep.join(array) + sep
    return list(array)


# https://stackoverflow.com/questions/13741998/is-there-a-way-to-let-classes-inherit-the-documentation-of-their-superclass-with
def copydoc(fromfunc: Callable, sep: str = '\n') -> Callable:
    """Decorator: Copy the docstring of `fromfunc`.

    :meta private:
    """
    def _decorator(func: Callable):
        sourcedoc = fromfunc.__doc__
        if func.__doc__ is None:
            func.__doc__ = sourcedoc
        elif sourcedoc is not None:
            func.__doc__ = sep.join([sourcedoc, func.__doc__])
        return func
    return _decorator


FuncType = TypeVar('FuncType')


class LazyString:
    """Evaluate function when conversion to string is requested."""

    def __init__(self, func, *args) -> None:
        """Construct 'LazyString' object."""
        self.value: Optional[str] = None
        self.func = func
        self.args = args

    def __str__(self) -> str:
        """Call the stored function."""
        if self.value is not None:
            return self.value
        self.value = str(self.func(*self.args))
        return self.value


def get_digest(data, algorithm: str = None) -> str:
    """Generate hexadecimal digest of data.

    Args:
        data: Binary data.
        algorithm: Optional; Algorithm to use instead of the default SHA1.
    Returns:
        Hexadecimal digest string.
    """
    if algorithm is None:
        algorithm = 'sha1'
    return hashlib.new(algorithm, data,
                       usedforsecurity=False).hexdigest()  # type: ignore[call-arg]


def json_dumps(obj: object) -> str:
    """Call json.dumps with correct indent."""
    return json.dumps(obj, indent=2)


def xml_dumps(obj: object, root_name: str) -> str:
    """Make sure that xml modules are loaded and create xml from dictionary or list."""

    def _xml_add(obj, element, name, indent=0) -> None:
        if isinstance(obj, dict):
            element.text = "\n" + (indent + 1) * "  "
            child = None
            for k, v in obj.items():
                child = ET.SubElement(element, str(k))
                _xml_add(v, child, str(k), indent + 1)
                child.tail = "\n" + (indent + 1) * "  "
            if child is not None:
                child.tail = "\n" + indent * "  "
            else:
                element.text = "\n" + indent * "  "

        elif (not isinstance(obj, str) and not isinstance(obj, bytes)
              and hasattr(obj, "__iter__")):
            element.text = "\n" + (indent + 1) * "  "
            if name[-1] == 's':
                childname = name[:-1]
            else:
                childname = "%s-item" % name
            child = None
            for val in iter(obj):
                child = ET.SubElement(element, childname)
                _xml_add(val, child, childname, indent + 1)
                child.tail = "\n" + (indent + 1) * "  "
            if child is not None:
                child.tail = "\n" + indent * "  "
            else:
                element.text = "\n" + indent * "  "
        else:
            element.text = str(obj)

    root = ET.Element(root_name)
    _xml_add(obj, root, root_name)
    return ET.tostring(root, encoding="utf-8",  # type: ignore
                       xml_declaration=False).decode("utf-8")


def is_mmb_file(fname: str) -> int:
    """Check if file is MMB based on size and extension.

    Returns: number of images in the MMB file or 0.
    """
    if not os.path.exists(fname):
        return 0

    fsize = os.path.getsize(fname)
    if fname.lower().endswith(".mmb"):
        if (fsize < MMB_INDEX_SIZE + MMB_DISK_SIZE or fsize > MMB_SIZE or
                (fsize - MMB_INDEX_SIZE) % MMB_DISK_SIZE != 0):
            raise ValueError("%s invalid MMB file size" % fname)
        return (fsize - MMB_INDEX_SIZE) // MMB_DISK_SIZE
    if fsize == MMB_SIZE:
        return MMB_MAX_ENTRIES
    return 0
