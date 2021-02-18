"""Command line interface module."""

# pylint: disable=redefined-builtin

import os
import sys
import glob
import codecs

from typing import Dict, Optional, List, cast

from .wildparse import argparse
from .wildparse.argparse import SUPPRESS, CustomHelpFormat

from .args import MyHelpFormatter

from .conv import bbc_to_unicode, unicode_to_bbc
from .misc import json_dumps, xml_dumps, get_digest, is_mmb_file
from .simplewarn import warn

from .enums import ListFormat, OpenMode, WarnMode, SizeOption, InfMode
from .enums import TranslationMode, DigestMode
from .sectors import Sectors
from .entry import Entry
from .side import Side
from .image import Image
from .mmbfile import MMBFile

DESCRIPTION = """BBC Micro Acorn DFS floppy disk image maintenance utility."""

IMAGE_OPTIONS_HELP = """
Image file options apply to the first following disk image file.
Those options must be specified before the corresponding image file name.
"""

IMPORT_FILE_OPTIONS_HELP = """
File options apply to the first following file name.
Those options override values read from the inf file.
"""

TRACKS_HELP = "Select between 80 and 40 track disks."

TRACKS_LONG_HELP = TRACKS_HELP + """
Default for existing disk images
is try to determine current disk format based on the image file size.
Default for new disk images is 80 tracks.
"""

SIDES_HELP = "Select between single and double sided disk images."

SIDES_LONG_HELP = SIDES_HELP + """
Default is to try to determine number of sides from disk extension
and size: files with extension `.dsd` are open as double sided,
other files are open as double sided based on their size.
Default for new images is two sides for images with `.dsd`
extension and one side for all other.
"""

SIDE_HELP = "Select disk side for double sided disks."

INDEX_HELP = "Select image index for MMB files."

INDEX_LONG_HELP = INDEX_HELP + """
In case of double sided disks, index 0 selects first side and index 1 selects
second side.
Alternatively index can be appended to the image file name separated
by colon. For example 'my_disk.dsd:1' or 'beeb.mmb:253'.
"""

LINEAR_HELP = "Select double sided disk data layout."

LINEAR_LONG_HELP = """
Select double sided disk data layout between
interleaved and linear. The interleaved format is more common
and more widely supported. In the interleaved format, track data
of each floppy side is interleaved - side 1 track 1,
side 2 track 1, side 1 track 2 etc... Image files with extension
`.dsd` are normally interleaved. Double sided image files with
extension `.ssd` are normally linear (in this case `s` stands for
"sequential"). Double sided `.ssd` are distinguished from single
sided by file size. For the theoretical 40 tracks, double sided
`.ssd` files, you would have to manually specify `-40`, `-D` and
`--linear`, because they cannot be reliably distinguished from
80 track single sided disk images.
"""

LIST_FORMAT_HELP = "Listing format. (default: cat)"

LIST_FORMAT_LONG_HELP = LIST_FORMAT_HELP + """
* raw - List file names.
* info - As displayed by *INFO command.
* inf - Format of .inf files.
* cat - As displayed by *CAT command.
* json - JSON format.
* xml - XML format.
* table - text table format
* dcat - As displayed by MMC *DCAT command
* CUSTOM_FORMAT - Formatting string - e.g. "{fullname:9} {size:06}".
See `--help-format` for available formatting keys.
"""

HEADER_FORMAT_HELP = "Listing header format. (default: based of list format)"

HEADER_FORMAT_LONG_HELP = HEADER_FORMAT_HELP + """
* cat - As displayed by *CAT command.
* table - text table format
* CUSTOM_FORMAT - Formatting string - e.g. "{title:12} {side}".
See `--help-format` for available formatting keys.
"""

IMAGE_HEADER_FORMAT_HELP = "Listing header common for entire image file."

IMAGE_HEADER_FORMAT_LONG_HELP = """
Listing header common for entire image file.
* CUSTOM_FORMAT - Formatting string - e.g. "{image_basename} {tracks}".
See `--help-format` for available formatting keys.
"""

SHRINK_HELP = """
Shrink disk image file to minimum size by trimming unused sectors."""

SHRINK_LONG_HELP = SHRINK_HELP + """
Such image files are smaller, but cannot be memory-mapped and may have to be
resized in flight by tools.
"""

INCLUDE_DRIVE_HELP = """
Include drive name (i.e. :0. or :2.) in inf files created from double sided
floppy images. The resulting inf files will be incompatible with most software.
Use this option with care.
"""

TRANSLATION_HELP = "Mode for translating dfs filename to \
host filename characters. (default: standard)"

TRANSLATION_LONG_HELP = TRANSLATION_HELP + """
* standard - replaces characters illegal on Windows with underscores.
* safe - replaces all characters, other than digits and letters with underscores.
"""

INF_LONG_HELP = """
Use of inf files.
* always - always create `.inf` files, fail import if inf file doesn't exist.
* auto - create `.inf` file if load or exec address is not 0, file is locked
  or filename cannot be directly translated to OS filename.
* never - never create `.inf` files and ignore existing inf files on import.
Default is `always` for export command and `auto` for import command.
"""

DATA_FORMAT_LONG_HELP = """
Data format. (default: raw)
* raw - read or write raw bytes.
* ascii - escape all non-readable or non-ascii characters.
* hex - hexadecimal dump.
"""

DIGEST_MODE_HELP = "Digest mode for file or disk side."

DIGEST_MODE_LONG_HELP = """
Digest mode for file:
* all - include all attributes.
* file - include load and execution addresses, but not access mode.
* data - only file contents, don't include load and execution addresses or access mode.
Digest mode for disk side:
* all - include all sectors.
* used - include used portions of catalog sectors and file sectors.
* file - files sorted alphabetically; Load and exec addresses are included
  in the digest. File access mode and disk attributes are not included.
"""

BOOTOPT_HELP = "Set disk boot option."

BOOTOPT_LONG_HELP = BOOTOPT_HELP + """
* off - No action.
* LOAD - Execute `*LOAD $.!BOOT` command.
* RUN - Execute `*RUN $.!BOOT` command.
* EXEC - Execute `*EXEC $.!BOOT` command.
"""

SEQNUM_HELP = "Set catalog sequence number."

SEQNUM_LONG_HELP = SEQNUM_HELP + """
Sequence number is a Binary Coded Decimal value incremented by the
Disk Filing System each time the disk catalog is modified.
"""

subcommands: Dict[str, argparse.ArgumentParser] = {}
options_template: List[argparse.ArgumentParser] = []


class _StoreConstOnceAction(argparse._StoreConstAction):  # pylint: disable=protected-access

    def __call__(self, parser, namespace, values, option_string=None):
        oldval = getattr(namespace, self.dest, None)
        if oldval is not None:
            parser.error("excessive argument %s" % argparse._get_action_name(self))
        setattr(namespace, self.dest, self.const)


class _StoreOnceAction(argparse._StoreAction):  # pylint: disable=protected-access

    def __call__(self, parser, namespace, values, option_string=None):
        oldval = getattr(namespace, self.dest, None)
        if oldval is not None:
            parser.error("excessive argument %s" % argparse._get_action_name(self))
        setattr(namespace, self.dest, values)


class _MyHelpAction(argparse.Action):
    def __init__(self, option_strings, metavar=None, dest=SUPPRESS,
                 default=SUPPRESS, help=None):
        super(_MyHelpAction, self).__init__(
            option_strings=option_strings, metavar=metavar, dest=dest,
            default=default, nargs='?', help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        if values is not None and values in subcommands:
            subcommands[values].print_help()
        else:
            parser.format_help()
            parser.print_help()
        parser.exit()


class _MyHelpOptionsAction(argparse.Action):
    def __init__(self, option_strings, metavar=None, dest=SUPPRESS,
                 default=SUPPRESS, help=None):
        super(_MyHelpOptionsAction, self).__init__(
            option_strings=option_strings, metavar=metavar, dest=dest,
            default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        options_template[0].print_help()
        parser.exit()


class _MyHelpFormatAction(argparse.Action):
    def __init__(self, option_strings, metavar=None, dest=SUPPRESS,
                 default=SUPPRESS, help=None):
        super(_MyHelpFormatAction, self).__init__(
            option_strings=option_strings, metavar=metavar, dest=dest,
            default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        _print_format_help()
        parser.exit()


def _glob_or_keep(pathname: str) -> List[str]:
    """Use globbing function on pathname, return original if nothing matches."""
    result = glob.glob(pathname)
    if len(result) == 0:
        return [pathname]
    return result


class _AddImageAction(argparse.Action):

    def __init__(self, option_strings, dest, nargs=None, const=None,
                 default=None, type=None, choices=None, required=False,
                 help=None, metavar=None):
        super(_AddImageAction, self).__init__(
            option_strings=option_strings, dest=dest, nargs=nargs,
            const=const, default=default, type=type,
            choices=choices, required=required, help=help,
            metavar=metavar)

    @staticmethod
    def _get_dest(parser, namespace):
        images = None
        selected = None

        if hasattr(namespace, "selected"):
            selected = getattr(namespace, "selected")
            namespace.selected = None
            if selected is None:
                parser.error("--to or --from is missing before image name")

            elif selected == "from":
                if namespace.from_image is not None:
                    parser.error("exactly one source image is required")
                if namespace.open_mode is not None and namespace.open_mode != OpenMode.EXISTING:
                    parser.error("arguments --new and --always are invalid "
                                 "for source image")
                images = []
                namespace.from_image = images

            elif selected == "to":
                if namespace.images is not None:
                    parser.error("exactly one destination image is required")
                images = []
                namespace.images = images

        else:
            images = namespace.images
            if images is None:
                images = []
                namespace.images = images

        return images

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) == 0:
            return

        images = self._get_dest(parser, namespace)
        if images is values:
            raise RuntimeError("adding value to itself")

        tracks = namespace.tracks
        sides = namespace.sides
        side = namespace.side
        index = namespace.index
        linear = namespace.linear
        open_mode = namespace.open_mode
        directory = namespace.directory

        expanded_values = []
        for pathname in values:
            expanded_values.extend(_glob_or_keep(pathname))
        values = expanded_values

        for name in values:
            images.append({'name': name, 'tracks': tracks,
                           'sides': sides, 'side': side, 'index': index,
                           'linear': linear, 'directory': directory,
                           'open_mode': open_mode})
            tracks = None
            sides = None
            side = None
            index = None
            linear = None
            directory = None
            open_mode = None

        namespace.tracks = None
        namespace.sides = None
        namespace.side = None
        namespace.index = None
        namespace.linear = None
        namespace.directory = None
        namespace.open_mode = None


class _AddImportAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) == 0:
            return

        load_addr = namespace.load_address
        exec_addr = namespace.exec_address
        locked = namespace.locked
        dfs_name = namespace.dfs_name
        files = namespace.files
        if files is None:
            files = []
            namespace.files = files

        expanded_values = []
        for pathname in values:
            expanded_values.extend(_glob_or_keep(pathname))
        values = expanded_values

        if (load_addr is not None or exec_addr is not None
                or locked is not None or dfs_name is not None):
            name = values[0]
            files.append({'name': name, 'load_addr': load_addr,
                          'exec_addr': exec_addr, 'locked': locked,
                          'dfs_name': dfs_name})
            values = values[1:]
            namespace.load_address = None
            namespace.exec_address = None
            namespace.locked = None
            namespace.dfs_name = None

        if len(values) != 0:
            files.append({'name': values, 'load_addr': None,
                          'exec_addr': None, 'locked': None,
                          'dfs_name': None})


def _open_from_params(params, for_write, warn_mode, existing=False):
    name = params["name"]
    sides = params["sides"]
    index = params["index"]
    tracks = params["tracks"]
    linear = params["linear"]
    open_mode = params["open_mode"]
    if existing:
        open_mode = OpenMode.EXISTING

    image = Image.open(name, for_write, open_mode, sides, tracks, linear,
                       warn_mode=warn_mode, index=index)

    try:
        if image.default_side is not None:
            if params["side"] is not None and params["side"] != image.default_side:
                raise ValueError("conflicting index and side specified")
        else:
            image.default_side = params["side"]
        image.current_dir = params["directory"]
    except:  # noqa: E722
        image.close()
        raise

    return image


def _conv_format(fmt):
    if not isinstance(fmt, str):
        return fmt
    fmt2 = fmt.lower()
    fmt = {'cat': ListFormat.CAT, 'info': ListFormat.INFO,
           'inf': ListFormat.INF, 'raw': ListFormat.RAW,
           'json': ListFormat.JSON, 'xml': ListFormat.XML,
           'table': ListFormat.TABLE, 'dcat': ListFormat.DCAT}.get(fmt2, fmt)
    return fmt


class _Process:
    def __init__(self, namespace):
        self.images = namespace.images
        self.warn_mode = getattr(namespace, "warn_mode", None)
        if self.warn_mode == "none":
            self.warn_mode = WarnMode.NONE
        elif self.warn_mode == "all":
            self.warn_mode = WarnMode.ALL
        else:
            self.warn_mode = None
        self.cont = getattr(namespace, "cont", None)
        self.verbose = (getattr(namespace, "verbose", 0)
                        + 1 - getattr(namespace, "quiet", 0))
        self.silent = getattr(namespace, "silent", None)

    @staticmethod
    def get_sector_number(image, sector):
        "Convert string to sector number"
        trk, _, sect = sector.partition('/')
        if len(sect) != 0:
            return int(trk), int(sect)
        return image.logical_to_physical(int(trk))

    def run_validate(self):
        """Run validate."""
        for params in self.images:
            try:
                _open_from_params(params, for_write=False,
                                  warn_mode=self.warn_mode).close()
            except (OSError, RuntimeError) as err:
                if not self.cont:
                    raise
                warn(err)
                continue


def _validate_command(namespace, _parser):
    _Process(namespace).run_validate()


def _get_mmb(name: str, index: Optional[int]):
    name2, _, index2 = name.rpartition(":")
    start = None
    end = None

    if name2 != '':
        index2, _, index3 = index2.partition("-")
        if not index2.isdigit():
            return None, None, None
        start = int(index2)
        if index is not None and index != start:
            raise ValueError("conflicting index number")
        if index3 != '':
            if not index3.isdigit():
                return None, None, None
            end = int(index3) + 1
        else:
            end = start + 1
        name = name2

    else:
        start = index
        if start is not None:
            end = start + 1

    if not is_mmb_file(name):
        return None, None, None

    return name, start, end


class _ListProcess(_Process):

    def _enable_only_images(self):
        if self.fmt not in (ListFormat.JSON, ListFormat.XML):
            if self.img_header_fmt is None:
                self.img_header_fmt = self.fmt
            self.fmt = ''
        self.header_fmt = None
        self.footer_fmt = None

    def _enable_only_files(self):
        self.root_node = "files"
        self.header_fmt = ''
        self.footer_fmt = None
        self.img_header_fmt = ''
        self.img_footer_fmt = None

    def _enable_only_sides(self):
        self.root_node = "sides"
        if self.fmt not in (ListFormat.JSON, ListFormat.XML):
            if self.header_fmt is None:
                self.header_fmt = self.fmt
            self.fmt = ''
        self.img_header_fmt = ''
        self.img_footer_fmt = ''

    def __init__(self, namespace):
        super().__init__(namespace)

        self.pattern = namespace.pattern
        if len(self.pattern) == 0:
            self.pattern = None

        self.sort = namespace.sort
        self.tree = []
        self.root_node = "images"
        self.fmt = _conv_format(namespace.list_format)
        self.header_fmt = _conv_format(namespace.header_format)
        self.footer_fmt = _conv_format(namespace.footer_format)
        self.img_header_fmt = _conv_format(namespace.image_header_format)
        self.img_footer_fmt = _conv_format(namespace.image_footer_format)
        self.only_images = namespace.only_images
        self.only_sides = namespace.only_sides
        self.only_files = namespace.only_files

        if self.only_files:
            self._enable_only_files()
        elif self.only_sides:
            self._enable_only_sides()
        elif self.only_images:
            self._enable_only_images()

    def _list_image(self, image, start: int = None, end: int = None):
        extra = {}
        if start is not None:
            extra["start_index"] = start
        if end is not None:
            extra["end_index"] = end
        if self.fmt in (ListFormat.JSON, ListFormat.XML):
            if self.only_images:
                prop = image.get_properties(for_format=False, recurse=False, **extra)
                self.tree.append(prop)
            elif self.only_sides:
                prop = image.get_properties(for_format=False, recurse=False, level=-1, **extra)
                self.tree.extend(prop)
            elif self.only_files:
                prop = image.get_properties(for_format=False, recurse=False, level=-2,
                                            pattern=self.pattern, sort=self.sort,
                                            silent=self.silent, **extra)
                self.tree.extend(prop)
            else:
                prop = image.get_properties(for_format=False, recurse=True,
                                            pattern=self.pattern, sort=self.sort,
                                            silent=self.silent, **extra)
                self.tree.append(prop)
        else:
            image.listing(fmt=self.fmt, pattern=self.pattern, side_header_fmt=self.header_fmt,
                          side_footer_fmt=self.footer_fmt, img_header_fmt=self.img_header_fmt,
                          img_footer_fmt=self.img_footer_fmt, sort=self.sort, silent=self.silent,
                          **extra)

    def run_listing(self):
        """Run listing."""
        for params in self.images:
            name, start, end = _get_mmb(params["name"], params["index"])
            if name is not None:
                with MMBFile.open(name, False) as mmb:
                    self._list_image(mmb, start, end)
            else:
                try:
                    with _open_from_params(params, for_write=False,
                                           warn_mode=self.warn_mode) as image:
                        self._list_image(image)
                except (OSError, RuntimeError) as err:
                    if not self.cont:
                        raise
                    warn(err)
                    continue
        if self.fmt == ListFormat.JSON:
            print(json_dumps(self.tree), end='\n')
        if self.fmt == ListFormat.XML:
            print(xml_dumps(self.tree, self.root_node))


def _list_command(namespace, _parser):
    _ListProcess(namespace).run_listing()


class _DumpProcess(_Process):

    def __init__(self, namespace, digest: bool = False):
        super().__init__(namespace)
        self.files = namespace.files
        self.tracks = namespace.track
        self.sectors = namespace.sector
        self.all = namespace.all
        self.dump_format = getattr(namespace, "dump_format", None)
        self.ellipsis = getattr(namespace, "ellipsis", None)
        self.width = getattr(namespace, "width", None)
        self.name = getattr(namespace, "name", None)
        self.digest = digest
        mode = getattr(namespace, "mode", None)
        if mode is None:
            self.mode = None
        elif mode == "all":
            self.mode = DigestMode.ALL
        elif mode == "used":
            self.mode = DigestMode.USED
        elif mode == "file":
            self.mode = DigestMode.FILE
        elif mode == "data":
            self.mode = DigestMode.DATA
        else:
            raise ValueError("invalid digest mode")
        self.algorithm = getattr(namespace, "algorithm", None)

    def dump(self, data: bytes):
        "Dump data"
        if self.dump_format == "raw":
            sys.stdout.buffer.write(data)

        elif self.dump_format == "text":
            newline = os.linesep
            str_data = newline.join(bbc_to_unicode(data.decode("ascii")).splitlines())
            if len(str_data) != 0:
                str_data = str_data + newline
            sys.stdout.write(str_data)

        elif self.dump_format == "ascii":
            print(codecs.escape_encode(data)[0].decode("ascii"))  # type: ignore

        else:
            Sectors.hexdump_buffer(data, width=self.width, ellipsis=self.ellipsis)

    def show_digest(self, image: Image, name: Optional[str],
                    drive: Optional[int], digest: str):
        "Show digest and optional name prefix"
        if self.name == 0:
            print(digest)
        else:
            prefix = ""
            if self.name > 1 or name is None:
                prefix = "%s:" % image.displayname
            if name is not None:
                if image.heads != 1 and drive is not None:
                    prefix += ":%d.%s" % (drive, name)
                else:
                    prefix += name
            print("%-32s %s" % (prefix, digest))

    def _dump_file(self, image, file):
        if not self.digest:
            self.dump(file.readall())
        else:
            digest = file.get_digest(self.mode, self.algorithm)
            self.show_digest(image, file.fullname, file.drive, digest)

    def _dump_files(self, image: Image):
        for file_pat in self.files:
            for file in image.get_files(file_pat, silent=self.silent):
                self._dump_file(image, file)
        if len(self.files) == 0:
            for file in image.get_files():
                self._dump_file(image, file)

    def _dump_all(self, image: Image):
        if not self.digest:
            data = b''.join(side.readall() for side in image.default_sides)
            self.dump(data)
        else:
            if image.default_side is None:
                self.show_digest(image, None, None, image.get_digest(self.algorithm))
            else:
                side: Side = image.default_sides[0]
                digest = side.get_digest(mode=self.mode, algorithm=self.algorithm)
                name = ":%d." % side.drive if image.heads != 1 else None
                self.show_digest(image, name, None, digest)

    def _dump_sectors(self, image: Image):
        if image.default_side is None:
            RuntimeError("select disk side")

        side = image.default_sides[0]
        for sector in self.sectors:
            start, _, end = sector.partition('-')
            track, sect = self.get_sector_number(image, start)
            if len(end) == 0:
                endsect = sect
                endtrack = track
            else:
                endtrack, endsect = self.get_sector_number(image, end)

            data = side.get_sectors(track, sect, endtrack, endsect+1).readall()
            if not self.digest:
                self.dump(data)
            else:
                digest = get_digest(data, self.algorithm)
                if endtrack != track or endsect != sect:
                    name = "[sectors %d/%d-%d/%d]" % (track, sect, endtrack, endsect)
                else:
                    name = "[sector %d/%d]" % (track, sect)
                self.show_digest(image, name, side.drive, digest)

    def _dump_tracks(self, image: Image):
        if image.default_side is None:
            RuntimeError("select disk side")

        side = image.default_sides[0]
        for track in self.tracks:
            start, _, end = track.partition('-')
            track = int(start)
            if len(end) == 0:
                endtrack = track
            else:
                endtrack = int(end)

            data = side.get_sectors(track, 0, endtrack+1, 0).readall()
            if not self.digest:
                self.dump(data)
            else:
                digest = get_digest(data, self.algorithm)
                if endtrack != track:
                    name = "[tracks %d-%d]" % (track, endtrack)
                else:
                    name = "[track %d]" % track
                self.show_digest(image, name, side.drive, digest)

    def _dump_image(self, image):
        if self.all:
            self._dump_all(image)

        elif self.sectors is not None and len(self.sectors) != 0:
            self._dump_sectors(image)

        elif self.tracks is not None and len(self.tracks) != 0:
            self._dump_tracks(image)

        else:
            self._dump_files(image)

    def _dump_mmb(self, mmb, start, end):
        for entry in mmb.all_entries:
            if start is not None and entry.index < start:
                continue
            if end is not None and entry.index >= end:
                continue
            if not entry.initialized and (start is None or end is None
                                          or end != start + 1):
                continue
            try:
                with entry.open(warn_mode=self.warn_mode) as image:
                    self._dump_image(image)
            except (OSError, RuntimeError) as err:
                if not self.cont:
                    raise
                warn(err)
                continue

    def run(self):
        "Run dump"
        for params in self.images:
            name, start, end = _get_mmb(params["name"], params["index"])
            if name is not None:
                with MMBFile.open(name, False) as mmb:
                    self._dump_mmb(mmb, start, end)
            else:
                try:
                    with _open_from_params(self.images[0], for_write=False,
                                           warn_mode=self.warn_mode) as image:
                        self._dump_image(image)
                except (OSError, RuntimeError) as err:
                    if not self.cont:
                        raise
                    warn(err)


def _dump_command(namespace, parser):
    if namespace.files is not None and len(namespace.files) > 0:
        if namespace.track is not None:
            parser.error("argument --track: not allowed with argument FILE")
        if namespace.sector is not None:
            parser.error("argument --sector: not allowed with argument FILE")
        if namespace.all:
            parser.error("argument --all: not allowed with argument FILE")
    if ((namespace.files is None or len(namespace.files) == 0)
            and namespace.track is None and namespace.sector is None
            and not namespace.all):
        parser.error("missing argument FILE")
    _DumpProcess(namespace).run()


def _digest_command(namespace, parser):
    if namespace.files is not None and len(namespace.files) > 0:
        if namespace.track is not None:
            parser.error("argument --track: not allowed with argument FILE")
        if namespace.sector is not None:
            parser.error("argument --sector: not allowed with argument FILE")
        if namespace.all:
            parser.error("argument --all: not allowed with argument FILE")
    _DumpProcess(namespace, True).run()


class _ModifyProcess(_Process):
    def __init__(self, namespace, _parser):
        super().__init__(namespace)
        self.save_option = (SizeOption.EXPAND if namespace.expand
                            else SizeOption.SHRINK if namespace.shrink
                            else None)
        self.compact = getattr(namespace, "compact", None)
        self.dlock = getattr(namespace, "dlock", None)
        self.dunlock = getattr(namespace, "dunlock", None)
        self.existing = False
        self.new_title = getattr(namespace, "new_title", None)
        self.title = getattr(namespace, "title", None)
        self.bootopt = getattr(namespace, "bootopt", None)
        self.sequence = getattr(namespace, "sequence", None)
        self.inf_mode = InfMode.AUTO
        if hasattr(namespace, "inf"):
            inf = getattr(namespace, "inf")
            if inf == "always":
                self.inf_mode = InfMode.ALWAYS
            elif inf == "never":
                self.inf_mode = InfMode.NEVER
        self.no_compact = True if self.compact is False else None
        self.ignore_access = getattr(namespace, "ignore_access", None)
        self.replace = getattr(namespace, "replace", None)
        self.file = getattr(namespace, "file", None)
        self.files = getattr(namespace, "files", None)
        self.oldname = getattr(namespace, "oldname", None)
        self.newname = getattr(namespace, "newname", None)
        self.from_image = getattr(namespace, "from_image", None)
        self.preserve_locked = getattr(namespace, "preserve_attr", None)
        self.tracks = getattr(namespace, "track", None)
        self.sectors = getattr(namespace, "sector", None)
        self.all = getattr(namespace, "all", None)
        self.dump_format = getattr(namespace, "dump_format", None)
        self.warn_mode2 = None
        self.directory = None
        self.command = None

    @staticmethod
    def get_arg(value: Optional[List], index: int):
        """Get parameter applicable to this side."""
        if value is None or len(value) <= index:
            return None
        return value[index]

    def run_per_side(self, image: Image, side: Side, index: int) -> None:
        """Apply operations to one side of floppy image."""
        value = self.get_arg(self.new_title, index)
        if value is not None and image.is_new_image:
            side.title = value
        value = self.get_arg(self.title, index)
        if value is not None:
            side.title = value
        value = self.get_arg(self.bootopt, index)
        if value is not None:
            side.opt_str = value
        value = self.get_arg(self.sequence, index)
        if value is not None:
            side.sequence_number = value

    @staticmethod
    def check_arg(arg_name, value, max_args):
        """Check for excessive argument."""
        if value is not None and len(value) > max_args:
            raise ValueError("excessive parameter '%s" % arg_name)

    def check_args(self, max_args):
        """Check for excessive arguments."""
        self.check_arg("--title", self.title, max_args)
        self.check_arg("--new-title", self.new_title, max_args)
        self.check_arg("--bootopt", self.bootopt, max_args)
        self.check_arg("--sequence", self.sequence, max_args)

    def _cmd_import(self, image: Image):
        count = 0
        for imp in self.files:
            os_file = cast(str, imp["name"])
            dfs_name = cast(Optional[str], imp["dfs_name"])
            load_addr = cast(Optional[int], imp["load_addr"])
            exec_addr = cast(Optional[int], imp["exec_addr"])
            locked = cast(Optional[bool], imp["locked"])
            count += image.import_files(
                os_files=os_file, dfs_names=dfs_name,
                inf_mode=self.inf_mode, load_addr=load_addr,
                exec_addr=exec_addr, locked=locked,
                replace=self.replace, ignore_access=self.ignore_access,
                no_compact=self.no_compact, continue_on_error=self.cont,
                verbose=(self.verbose > 1), silent=self.silent)
        if self.verbose:
            print("%s: %d files imported" % (image.displayname, count))

    def _read_stdin(self) -> bytes:
        if self.dump_format == "raw":
            return sys.stdin.buffer.read()

        if self.dump_format == "text":
            data = b'\r'.join(unicode_to_bbc(sys.stdin.read()).encode("ascii").splitlines())
            if len(data) != 0:
                data = data + b'\r'
            return data

        if self.dump_format == "ascii":
            return codecs.escape_decode(  # type: ignore
                sys.stdin.read().encode("ascii"))[0]

        return Sectors.decode_hexdump(sys.stdin.read())

    def _build_files(self, image: Image):
        for file in self.files:
            names = file["name"]
            load_addr = file["load_addr"]
            exec_addr = file["exec_addr"]
            locked = file["locked"]

            if isinstance(names, str):
                names = [names]

            for name in names:
                image.add_file(name, self._read_stdin(), load_addr=load_addr,
                               exec_addr=exec_addr, locked=locked,
                               replace=self.replace,
                               ignore_access=self.ignore_access,
                               no_compact=self.no_compact)

    def _build_all(self, image: Image):
        sectors = Sectors(image, [], 0, 0)
        for side in image.default_sides:
            sectors.extend(side.get_all_sectors())
        sectors.writeall(self._read_stdin())
        if self.warn_mode != WarnMode.NONE:
            image.validate(self.warn_mode == WarnMode.ALL)

    def _build_sectors(self, image: Image):
        if image.default_side is None:
            RuntimeError("select disk side")

        for sector in self.sectors:
            start, _, end = sector.partition('-')
            track, sect = self.get_sector_number(image, start)
            if len(end) == 0:
                endsect = sect
                endtrack = track
            else:
                endtrack, endsect = self.get_sector_number(image, end)
            sectors = image.default_sides[0].get_sectors(track, sect, endtrack, endsect+1)
            sectors.writeall(self._read_stdin())

        if self.warn_mode != WarnMode.NONE:
            image.validate(self.warn_mode == WarnMode.ALL)

    def _build_tracks(self, image: Image):
        if image.default_side is None:
            RuntimeError("select disk side")

        for track in self.tracks:
            start, _, end = track.partition('-')
            track = int(start)
            if len(end) == 0:
                endtrack = track
            else:
                endtrack = int(end)
            sectors = image.default_sides[0].get_sectors(track, 0, endtrack+1, 0)
            sectors.writeall(self._read_stdin())

        if self.warn_mode != WarnMode.NONE:
            image.validate(self.warn_mode == WarnMode.ALL)

    def _cmd_build(self, image: Image):
        if self.files is not None and len(self.files) != 0:
            self._build_files(image)

        if self.all:
            self._build_all(image)

        if self.sectors is not None and len(self.sectors) != 0:
            self._build_sectors(image)

        if self.tracks is not None and len(self.tracks) != 0:
            self._build_tracks(image)

    def _cmd_attrib(self, image: Image):
        count = 0
        for fileset in self.files:
            patterns = fileset["name"]
            load_addr = fileset["load_addr"]
            exec_addr = fileset["exec_addr"]
            locked = fileset["locked"]
            entries = image.get_files(patterns, silent=self.silent)
            count += len(entries)
            for entry in entries:
                if load_addr is not None:
                    entry.load_address = load_addr
                if exec_addr is not None:
                    entry.exec_address = exec_addr
                if locked is not None:
                    entry.locked = locked
        if self.verbose:
            print("%s: %d files changed" % (image.displayname, count))

    def _cmd_format(self, image: Image):
        image.format()
        if self.verbose:
            print("%s: formatted" % image.displayname)

    def _cmd_dkill(self, image: Image):
        if image.dkill():
            if self.verbose:
                print("%s: set uninitialized status" % image.displayname)

    def _cmd_drestore(self, image: Image):
        if image.drestore(self.warn_mode2):
            if self.verbose:
                print("%s: restored initialized status" % image.displayname)

    def _cmd_delete(self, image: Image):
        if image.delete(filename=self.file,
                        ignore_access=self.ignore_access,
                        silent=self.silent):
            if self.verbose:
                print("%s: file '%s' deleted" % (image.displayname, self.file))

    def _cmd_destroy(self, image: Image):
        count = image.destroy(pattern=self.files,
                              ignore_access=self.ignore_access,
                              silent=self.silent)
        if self.verbose:
            print("%s: %d files deleted" % (image.displayname, count))

    def _cmd_lock(self, image: Image):
        count = image.lock(pattern=self.files, silent=self.silent)
        if self.verbose:
            print("%s: %d files locked" % (image.displayname, count))

    def _cmd_unlock(self, image: Image):
        count = image.unlock(pattern=self.files, silent=self.silent)
        if self.verbose:
            print("%s: %d files unlocked" % (image.displayname, count))

    def _cmd_rename(self, image: Image):
        if image.rename(from_name=self.oldname, to_name=self.newname,
                        replace=self.replace, ignore_access=self.ignore_access,
                        no_compact=self.no_compact, silent=self.silent):
            if self.verbose:
                print("%s: file '%s' renamed to '%s'"
                      % (image.displayname, self.oldname, self.newname))

    def _cmd_copy(self, image: Image):
        if image.copy(from_name=self.oldname, to_name=self.newname,
                      replace=self.replace, ignore_access=self.ignore_access,
                      no_compact=self.no_compact,
                      preserve_attr=self.preserve_locked, silent=self.silent):
            if self.verbose:
                print("%s: file '%s' copied to '%s'"
                      % (image.displayname, self.oldname, self.newname))

    def _cmd_backup(self, image: Image):
        with _open_from_params(self.from_image[0], for_write=False,
                               warn_mode=self.warn_mode2) as src_image:
            image.backup(source=src_image, warn_mode=WarnMode.NONE)
            if self.verbose:
                print("%s: copied from %s" % (image.displayname, src_image.displayname))

    def _cmd_copyover(self, image: Image):
        with _open_from_params(self.from_image[0], for_write=False,
                               warn_mode=self.warn_mode) as src_image:
            count = image.copy_over(source=src_image, pattern=self.files,
                                    replace=self.replace,
                                    ignore_access=self.ignore_access,
                                    no_compact=self.no_compact,
                                    change_dir=self.directory is not None,
                                    preserve_attr=self.preserve_locked,
                                    continue_on_error=self.cont,
                                    verbose=(self.verbose > 1),
                                    silent=self.silent)
            if self.verbose:
                print("%s: %d files copied from %s"
                      % (image.displayname, count, src_image.displayname))

    def run_image(self, image: Image, params: Dict) -> None:
        """Apply operations to single image file."""

        self.directory = params['directory']
        if self.dunlock and image.locked:
            image.locked = False
            if self.verbose:
                print("%s: image unlocked" % image.displayname)

        if self.command is not None:
            self.command(image)

        if self.compact:
            image.compact()

        sides = image.default_sides
        self.check_args(len(sides))
        index = 0
        for side in sides:
            self.run_per_side(image, side, index)
            index += 1

        if self.dlock and not image.locked:
            image.locked = True
            if self.verbose:
                print("%s: image locked" % image.displayname)

        if image.modified or self.save_option != SizeOption.KEEP:
            image.save(self.save_option)
        image.close()

    def run(self) -> None:
        """Execute command on all images."""
        for params in self.images:
            with _open_from_params(params, for_write=True, warn_mode=self.warn_mode,
                                   existing=self.existing) as image:
                self.run_image(image, params)


def _create_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.run()


def _format_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    # Skip validation if contents are going to be overwritten
    proc.warn_mode2 = proc.warn_mode
    proc.warn_mode = WarnMode.NONE
    proc.command = proc._cmd_format
    proc.run()


def _dkill_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.command = proc._cmd_dkill
    proc.run()


def _drestore_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    # Skip validation on open
    proc.warn_mode2 = proc.warn_mode
    proc.warn_mode = WarnMode.NONE
    proc.command = proc._cmd_drestore
    proc.run()


def _import_command(namespace, parser):
    if namespace.files is None or len(namespace.files) == 0:
        parser.error("parameter FILE is required")
    proc = _ModifyProcess(namespace, parser)
    proc.command = proc._cmd_import
    proc.run()


def _delete_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.existing = True
    proc.command = proc._cmd_delete
    proc.run()


def _lock_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.existing = True
    proc.command = proc._cmd_lock
    proc.run()


def _unlock_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.existing = True
    proc.command = proc._cmd_unlock
    proc.run()


def _destroy_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.existing = True
    proc.command = proc._cmd_destroy
    proc.run()


def _copy_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.existing = True
    proc.command = proc._cmd_copy
    proc.run()


def _rename_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.existing = True
    proc.command = proc._cmd_rename
    proc.run()


def _backup_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    # Skip validation if contents are going to be overwritten
    proc.warn_mode2 = proc.warn_mode
    proc.warn_mode = WarnMode.NONE
    proc.command = proc._cmd_backup
    proc.run()


def _copyover_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.command = proc._cmd_copyover
    proc.run()


def _attrib_command(namespace, parser):
    proc = _ModifyProcess(namespace, parser)
    proc.existing = True
    proc.command = proc._cmd_attrib
    proc.run()


def _build_command(namespace, parser):
    if namespace.files is not None and len(namespace.files) > 0:
        if namespace.track is not None:
            parser.error("argument --track: not allowed with argument FILE")
        if namespace.sector is not None:
            parser.error("argument --sector: not allowed with argument FILE")
        if namespace.all:
            parser.error("argument --all: not allowed with argument FILE")
    if ((namespace.files is None or len(namespace.files) == 0)
            and namespace.track is None and namespace.sector is None
            and not namespace.all):
        parser.error("missing argument FILE")
    proc = _ModifyProcess(namespace, parser)
    proc.command = proc._cmd_build
    proc.run()


class _ExportProcess(_Process):

    def __init__(self, namespace):
        super().__init__(namespace)

        self.pattern = namespace.pattern
        if len(self.pattern) == 0:
            self.pattern = None
        self.inf_mode = InfMode.ALWAYS
        if hasattr(namespace, "inf"):
            inf = getattr(namespace, "inf")
            if inf == "auto":
                self.inf_mode = InfMode.AUTO
            elif inf == "never":
                self.inf_mode = InfMode.NEVER
        self.output = namespace.output
        self.replace = getattr(namespace, "replace", None)
        self.create_dir = getattr(namespace, "create_dir", None)
        self.xlate = TranslationMode.STANDARD
        if hasattr(namespace, "translation"):
            xlate = getattr(namespace, "translation")
            if xlate == "safe":
                self.xlate = TranslationMode.SAFE
        self.include_drive = getattr(namespace, "include_drive_name", None)

    def _export_image(self, image):
        count = image.export_files(
            output=self.output, files=self.pattern,
            create_directories=self.create_dir,
            translation=self.xlate,
            inf_mode=self.inf_mode,
            include_drive=self.include_drive,
            replace=self.replace,
            continue_on_error=self.cont,
            verbose=(self.verbose > 1),
            silent=self.silent)
        if self.verbose:
            print("%s: %d files exported" % (image.displayname, count))

    def run(self):
        """Run export on all images."""
        for params in self.images:
            try:
                with _open_from_params(params, for_write=False,
                                       warn_mode=self.warn_mode) as image:
                    self._export_image(image)
            except OSError as err:
                if not self.cont:
                    raise
                warn(err)


def _export_command(namespace, _parser):
    _ExportProcess(namespace).run()


WARN_HELP = "Validation warnings display mode. (default: first)"

WARN_LONG_HELP = WARN_HELP + """
 * none - Don't display validation warnings.
 * first - Display first warning and skip further validation
 * all - Display all validation warning. Some warnings may be redundant.
"""


def _add_global_options(parser, subparser=True, template=False):
    # pylint: disable=protected-access
    try:
        parser._optionals.title = "options"
        parser._optionals.group_usage = False
    except AttributeError:
        pass

    if subparser:
        global_options = parser.add_argument_group("global options")
        add = global_options.add_argument
        add('-h', '--help', action='help', help=SUPPRESS)

        parser.set_defaults(warn_mode=None)
        add('--warn', choices=['none', 'first', 'all'],
            help=WARN_LONG_HELP if template else WARN_HELP,
            dest='warn_mode')
        add('-v', '--verbose', action='count',
            help='Verbose mode - list copied files.', default=0)
        add('-q', '--quiet', action='count',
            help='Quiet mode - don\'t report successful operations.', default=0)
        add('--continue', dest='cont', help='Continue on non-fatal errors.',
            action=argparse.BooleanOptionalAction, default=True)  # pylint: disable=no-member
        add('-s', '--silent', action='store_true',
            help="Don't generate error if a file doesn't exist.")


def _drecat_command(namespace, _parser):
    proc = _Process(namespace)
    for mmb_name in namespace.images:
        with MMBFile.open(mmb_name, True) as mmb:
            count = mmb.drecat(proc.warn_mode)
            if proc.verbose:
                print("%s: %d entries updated" % (mmb_name, count))


def _donboot_command(namespace, _parser):
    set_onboot = namespace.set_onboot
    proc = _Process(namespace)
    for mmb_name in namespace.images:
        with MMBFile.open(mmb_name, True) as mmb:
            for drive, index in set_onboot:
                mmb.onboot[drive] = index
            if proc.verbose or len(set_onboot) == 0:
                for i in range(4):
                    print("%2d:%s" % (i, mmb.all_entries[mmb.onboot[i]]))


def _create_mmb_command(namespace, _parser):
    proc = _Process(namespace)
    for mmb_name in namespace.images:
        with MMBFile.create(mmb_name):
            pass
        if proc.verbose:
            print("%s: file created" % mmb_name)


PATTERN_HELP = "File name or pattern for listing."

PATTERN_LONG_HELP = """
File name or pattern. The `fnmatch` function is used for pattern matching:
* pattern `*` matches any string,
* pattern `?` matches any single character,
* pattern `[seq]` matches any character in `seq`,
* pattern `[!seq]` matches any character not in `seq`.
If directory-matching part (e.g. `?.`) is not present in the pattern,
only files in the default directory are matched.
"""


def _add_list_options(parser, index, template=False, group=None):
    if group is None:
        if template:
            list_options = parser.add_argument_group('command options')
        else:
            list_options = parser.add_argument_group('listing options')
        list_options.group_usage = True
    else:
        list_options = group

    add = list_options.add_argument

    if index:
        add('-p', '--pattern',
            help=PATTERN_LONG_HELP if template else PATTERN_HELP,
            nargs=1, action='extend', default=[])

    add('-f', '--list-format', metavar='{cat,info,raw,inf,json,xml,table,dcat,CUSTOM_FORMAT}',
        help=LIST_FORMAT_LONG_HELP if template else LIST_FORMAT_HELP,
        dest="list_format")
    add('--sort', help="Sort files by name.", dest="sort",
        action=argparse.BooleanOptionalAction, default=None)  # pylint: disable=no-member
    add('--header-format', metavar='{cat,table,CUSTOM_FORMAT}',
        help=HEADER_FORMAT_LONG_HELP if template else HEADER_FORMAT_HELP)
    add('--footer-format', metavar='CUSTOM_FORMAT',
        help="Listing footer format. Available keys are the same as for header.")
    add('--image-header-format', metavar='CUSTOM_FORMAT',
        help=IMAGE_HEADER_FORMAT_LONG_HELP if template else IMAGE_HEADER_FORMAT_HELP)
    add('--image-footer-format', metavar='CUSTOM_FORMAT',
        help="Image Listing footer format. Available keys are the same as for image header.")

    group = list_options.add_mutually_exclusive_group()
    add = group.add_argument
    add('--only-files', action='store_true', help="Include only files in listing - "
        "useful mainly for JSON, XML and table format")
    add('--only-sides', action='store_true', help="Include only disk sides in listing - "
        "useful mainly for JSON, XML and table format")
    add('--only-images', action='store_true', help="Include only disk images in listing - "
        "useful mainly for JSON, XML and table format")
    return list_options


def _add_modify_options(parser, command):
    modify_options = parser.add_argument_group('image modify options')
    modify_options.group_usage = True

    if command in ("create", "import", "copy-over", "build", "template"):
        group = modify_options.add_mutually_exclusive_group()
        add = group.add_argument
        add('--title', action='append', help='Set disk title.')
        add('--new-title', action='append', metavar='TITLE',
            help='Set disk title for newly created disk images.')
    elif command in ("format", "backup"):
        add = modify_options.add_argument
        add('--title', action='append', help='Set disk title.')
    modify_options.set_defaults(title=None)
    modify_options.set_defaults(new_title=None)

    add = modify_options.add_argument
    if command in ("create", "import", "copy-over", "build", "format",
                   "backup", "template"):
        add('--bootopt', action='append', choices=['off', 'LOAD', 'RUN', 'EXEC'],
            help=BOOTOPT_LONG_HELP if command == "template" else BOOTOPT_HELP)
        add('--sequence', action='append',
            help=SEQNUM_LONG_HELP if command == "template" else SEQNUM_HELP,
            type=int)
    modify_options.set_defaults(bootopt=None)
    modify_options.set_defaults(sequence=None)
    if command not in ("format", "dkill", "drestore"):
        add('--compact', action=argparse.BooleanOptionalAction,  # pylint: disable=no-member
            help='Coalesce fragmented free space on disk. Default is to compact '
            'disk if needed to make space for new file.')
    modify_options.set_defaults(compact=None)

    if command != "dkill":
        add('--dlock', action='store_true', help="Set disk image locked flag in MMB index")

    if command != "drestore":
        add('--dunlock', action='store_true', help="Reset disk image locked flag in MMB index")

    if command not in ("dkill", "drestore"):
        group = modify_options.add_mutually_exclusive_group()
        add = group.add_argument
        add('--shrink', action='store_true',
            help=SHRINK_LONG_HELP if command == "template" else SHRINK_HELP)
        add('--expand', action='store_true', help="Expand disk image file to maximum size.")
    modify_options.set_defaults(shrink=None)
    modify_options.set_defaults(expand=None)


def _add_image_arg(parser, nargs):
    parser.set_defaults(open_mode=None)
    parser.set_defaults(tracks=None)
    parser.set_defaults(sides=None)
    parser.set_defaults(linear=None)
    parser.set_defaults(side=None)
    parser.set_defaults(index=None)
    parser.set_defaults(directory=None)

    if nargs is not None:
        add = parser.add_argument
        add('images', metavar='IMAGE', nargs=nargs, help='Floppy disk image.',
            action=_AddImageAction)


def _add_image_options(parser, existing, nargs, template=False, command=None):

    image_options = parser.add_argument_group('image file options', IMAGE_OPTIONS_HELP)

    add = image_options.add_argument
    if not existing:
        add('--new', help='Create new image file. Fail if file already exists.',
            action=_StoreConstOnceAction, const=OpenMode.NEW, dest='open_mode')
        add('--existing', help="Open existing image. Fail if file doesn't exist.",
            action=_StoreConstOnceAction, const=OpenMode.EXISTING, dest='open_mode')
        add('--always', help="Create new image or open existing image,. This is the default.",
            action=_StoreConstOnceAction, const=OpenMode.ALWAYS, dest='open_mode')

    if template:
        add('-80', '-40', '--tracks', choices=[80, 40], help=TRACKS_LONG_HELP)
        add('-S', '-D', '--sides', choices=[1, 2], help=SIDES_LONG_HELP)
        add('-I', '-L', '--interleaved', '--linear', action='store_true',
            help=LINEAR_LONG_HELP)
        add('-1', '-2', '--side', choices=[1, 2], help=SIDE_HELP)
        add('-i', '--index', type=int, help=INDEX_LONG_HELP)

    else:
        if command not in ("dkill", "drestore"):
            add('-80', help='80 tracks disk.', action=_StoreConstOnceAction,
                const=80, dest='tracks')
            add('-40', help='40 tracks disk.', action=_StoreConstOnceAction,
                const=40, dest='tracks')
            add('--tracks', action=_StoreOnceAction, choices=[80, 40], help=TRACKS_HELP)
            add('-S', help='Single sided floppy image.', action=_StoreConstOnceAction,
                const=1, dest='sides')
            add('-D', help='Double sided floppy image.', action=_StoreConstOnceAction,
                const=2, dest='sides')
            add('--sides', action=_StoreOnceAction, choices=[1, 2], help=SIDES_HELP)
            add('-I', '--interleaved', help='Interleaved double sided disk layout.',
                action=_StoreConstOnceAction, const=False, dest='linear')
            add('-L', '--linear', help='Linear double sided disk layout',
                action=_StoreConstOnceAction, const=True, dest='linear')
            if command != "validate":
                add('-1', help='Select first side.', action=_StoreConstOnceAction,
                    const=1, dest='side')
                add('-2', help='Select second side.', action=_StoreConstOnceAction,
                    const=2, dest='side')
                add('--side', action=_StoreOnceAction, choices=[1, 2], help=SIDE_HELP)

        add('-i', '--index', action=_StoreOnceAction, type=int, help=INDEX_HELP)

    if command not in ("validate", "dkill", "drestore"):
        add = image_options.add_argument
        add('-d', '--directory', help="Default DFS directory.")

    _add_image_arg(parser, nargs)


def _hexint(string):
    """Convert argument to hex."""
    return int(string, 16)


BUILD_FILE_OPTIONS_HELP = "File options apply to the first following file name."

ATTRIB_FILE_OPTIONS_HELP = "File options apply to the first following group of file names."


def _add_import_file_options(parser, command):
    if command == "build":
        help = BUILD_FILE_OPTIONS_HELP
    elif command == "attrib":
        help = ATTRIB_FILE_OPTIONS_HELP
    else:
        help = IMPORT_FILE_OPTIONS_HELP
    import_file_options = parser.add_argument_group('file options',
                                                    description=help)
    import_file_options.group_usage = True
    add = import_file_options.add_argument
    add('--load-address', metavar='ADDRESS', type=_hexint,
        help="Load address for the following file. Must be a hexadecimal number.")
    add('--exec-address', metavar='ADDRESS', type=_hexint,
        help="Exec address for the following file. Must be a hexadecimal number.")
    add('--locked', action=argparse.BooleanOptionalAction,  # pylint: disable=no-member
        help="Set locked attribute.")
    import_file_options.set_defaults(locked=None)

    if command in ("import", "template"):
        add = import_file_options.add_argument
        add('--dfs-name', metavar='NAME', help='DFS name for the imported file.')
    else:
        import_file_options.set_defaults(dfs_name=None)

    if command != "template":
        help = "Files to import." if command == "import" else "Files."
        add = parser.add_argument
        add('files', metavar='FILE', nargs='**', help=help,
            action=_AddImportAction)


def _add_command_options(parser, command, opts=None):
    if opts is None:
        opts = parser.add_argument_group('%s options' % command)
    opts.group_usage = True
    add = opts.add_argument

    if command == "export":
        add('-p', '--pattern', help='File name or pattern for export.',
            nargs=1, action='extend', default=[])

    if command in ("export", "command"):
        add('--create-dir', action=argparse.BooleanOptionalAction,  # pylint: disable=no-member
            help="Create output directories as needed.", default=False)
        add('--translation', choices=['standard', 'safe'],
            help=TRANSLATION_LONG_HELP if command == "command" else TRANSLATION_HELP,
            default="standard")
        add('--include-drive-name', action='store_true',
            help=INCLUDE_DRIVE_HELP)

    if command in ("import", "export", "command"):
        default = "always" if command == "export" else "auto"
        help = "Use of inf files. (default: %s)" % default
        add('--inf', action='store', choices=['always', 'auto', 'never'],
            help=INF_LONG_HELP if command == "command" else help)

    if command in ("build", "rename", "copy", "import", "export", "copy-over", "command"):
        add('--replace', action=argparse.BooleanOptionalAction,  # pylint: disable=no-member
            help="Allow replacing existing files.", default=False)

    if command in ("build", "delete", "rename", "copy", "destroy",
                   "import", "copy-over", "command"):
        add('--ignore-access', action=argparse.BooleanOptionalAction,  # pylint: disable=no-member
            help="Allow deleting or replacing locked files.", default=False)

    if command in ("copy", "copy-over", "command"):
        default = (command == "copy-over")
        add('--preserve-attr', action=argparse.BooleanOptionalAction,  # pylint: disable=no-member
            help="Preserve 'locked' attribute on copying.", default=default)


def _add_dump_options(parser, command, group=None):
    if group is None:
        group = parser.add_argument_group("%s options" % command)
    add = group.add_argument
    if command in ("dump", "build"):
        add("-f", "--format", choices=['raw', 'text', 'ascii', 'hex'],
            dest="dump_format",
            help="Data format. (default: raw)", default="raw")
    elif command == "command":
        add("--format", choices=['raw', 'text', 'ascii', 'hex'],
            dest="dump_format",
            help=DATA_FORMAT_LONG_HELP, default="raw")
    if command in ("dump", "command"):
        add("--ellipsis", help="Skip repeating lines in hex dump.",
            action=argparse.BooleanOptionalAction,  # pylint: disable=no-member
            default=True)
        add("--width", help="Bytes per line in hex dump.", type=int)
    if command == "build":
        _add_command_options(parser, command, group)
    if command in ("digest", "command"):
        add("-n", "--name", help="Display each file or object name. "
                                 "Repeat for image name.",
            action="count", default=0)
        add("-m", "--mode", choices=["all", "used", "file", "data"],
            help=DIGEST_MODE_LONG_HELP if command == "command" else DIGEST_MODE_HELP,
            default=None)
        add("-a", "--algorithm", help="Digest algorithm, e.g. sha1, sha256, md5",
            default=None)

    group = group.add_mutually_exclusive_group()
    group.add_argument("--sector", help="Process sectors instead of files. "
                                        "Argument can be a range of sectors, with start and end "
                                        "separated by a dash. Physical sector "
                                        "address format is 'track/sector'.",
                       action='append')
    group.add_argument("--track", help="Process tracks instead of files.  "
                                       "Argument can be a range of tracks, with start and end "
                                       "separated by a dash.",
                       action='append')
    group.add_argument("--all", help="Process entire disk or disk side.",
                       action='store_true')


def _add_subcommand(subparsers, prog, command, help, format, no_prog=False,
                    no_global=False, **kwargs):
    if not no_prog:
        prog = "%s %s" % (prog, command)
    cmd = subparsers.add_parser(command, add_help=False,
                                description=help,
                                prog=prog,
                                help=help, formatter_class=format, **kwargs)
    cmd.greedy_star = True
    subcommands[command] = cmd
    if not no_global:
        _add_global_options(cmd)
    return cmd


def _add_2images_arg(group, _command):
    add = group.add_argument
    add("--from", action=_StoreConstOnceAction, const='from', dest="selected",
        required=True, help=SUPPRESS)
    add('from_image', metavar='--from FROM_IMAGE', help='Source image file.',
        action=_AddImageAction, nargs=1)
    add("--to", action=_StoreConstOnceAction, const='to', dest="selected",
        required=True, help=SUPPRESS)
    add('images', metavar='--to TO_IMAGE', help='Destination image file.',
        action=_AddImageAction, nargs=1)
    group.set_defaults(selected=None)


def _add_files_arg(parser, command):
    parser.add_argument('files', metavar='FILES', help=('Files to %s.' % command),
                        nargs='+', action='store')


def _add_2file_arg(parser, _command):
    parser.add_argument('oldname', metavar='FROM', help='Old name.')
    parser.add_argument('newname', metavar='TO', help='New name.')


def _print_format_help():
    print("File properties can be used as keyword arguments in formatting string passed as "
          "`--list-format` argument for `list` command or "
          "`--output` argument for `export` command.")
    print("File properties are:")
    for keyword, descr in Entry.PROPERTY_NAMES.items():
        print("* %-20s - %s" % (keyword, descr))
    print("\nFloppy disk side properties can be used as keyword arguments in formatting "
          "string passed as `--header-format` or `--footer-format` for `list` command.")
    print("Disk side properties are:")
    for keyword, descr in Side.PROPERTY_NAMES.items():
        print("* %-20s - %s" % (keyword, descr))
    print("\nImage file properties can be used as keyword arguments in formatting "
          "string passed as `--image-header-format` or `--image-footer-format` "
          "for `list` command.")
    print("Image file properties are:")
    for keyword, descr in Image.PROPERTY_NAMES.items():
        print("* %-20s - %s" % (keyword, descr))


GLOBAL_USAGE = '%(prog)s COMMAND ...\n-h [COMMAND]'

INDEX_USAGE = ('%(prog)s [global options] [listing options] ([image file options] IMAGE)...\n'
               'cat [global options] [listing options] ([image file options] IMAGE)...\n'
               'index [global options] [listing options] ([image file options] IMAGE)...')

INDEX_EPILOG = """examples:
  dfsimage list x.ssd

  dfsimage list --image-header="Image {image_filename}" \
                --header="Side {side}" --list-format="{fullname:12} {sha1}" img/*.dsd
"""

CREATE_USAGE = ('%(prog)s [global options] [image modify options] [image file options] IMAGE\n'
                'modify [global options] [image modify options] [image file options] IMAGE')

CREATE_EPILOG = """examples:
  dfsimage create --new -D -L --title=Side1 --title=Side2 linear.img

  dfsimage modify --existing image.ssd --bootopt=EXEC
"""

BACKUP_USAGE = ('%(prog)s [global options] [image modify options] '
                '--from [image file options] FROM_IMAGE --to [image file options] TO_IMAGE\n'
                'convert [global options] [image modify options] '
                '--from [image file options] FROM_IMAGE --to [image file options] TO_IMAGE\n'
                'copy-disk [global options] [image modify options] '
                '--from [image file options] FROM_IMAGE --to [image file options] TO_IMAGE')

BACKUP_EPILOG = """examples:
  dfsimage convert --from -D -L linear.img --to inter.dsd

  dfsimage backup --from -2 dual.dsd --to side2.ssd

  dfsimage copy-disk --from beeb.mmc:123 --to my_disk.ssd
"""

IMPORT_USAGE = ('%(prog)s [global options] [import options] [image modify options] '
                '[image file options] IMAGE ([file options] FILE)...')

IMPORT_EPILOG = """examples:
  dfsimage import --new newfloppy.ssd --title="New floppy" files/*

  dfsimage import floppy.dsd --replace --ignore-access --load-addr=FF1900 --exec-addr=FF8023 \
      --locked --dfs-name=":2.$.MY_PROG" my_prog.bin
"""

EXPORT_USAGE = ('%(prog)s [global options] [export options] -o OUTPUT '
                '([image file options] IMAGE)...')

EXPORT_EPILOG = """examples:
  dfsimage export floppy.ssd -o floppy/ -p "A.*"

  dfsimage export img/*.dsd --create-dir -o 'output/{image_basename}/{drive}.{fullname}'
"""

DUMP_USAGE = ('%(prog)s [global options] [dump options] [image file options] IMAGE FILE...\n'
              'read [global options] [dump options] [image file options] IMAGE FILE...')

DUMP_EPILOG = """examples:
  dfsimage dump image.ssd -f hex MY_PROG

  dfsimage dump image.ssd -f raw --sector=0-1 > cat-sectors.bin
"""

BUILD_USAGE = ('%(prog)s [global options] [build options] [image modify options] '
               '[image file options] IMAGE ([file options] FILE)...\n'
               'write [global options] [build options] [image modify options] '
               '[image file options] IMAGE ([file options] FILE)...')

BUILD_EPILOG = """examples:
  dfsimage list image.ssd | dfsimage build -f text image.ssd CATALOG

  dfsimage write image.ssd --sector=0-1 < cat-sectors.bin
"""

COPYOVER_USAGE = ('%(prog)s [global options] [copy-over options] [image modify options] '
                  '--from [image file options] FROM_IMAGE --to [image file options] TO_IMAGE '
                  'FILES...')
COPYOVER_EPILOG = """examples:
  dfsimage copy-over --from image.ssd --to another.ssd "?.BLAG*"
"""

FORMAT_EPILOG = """examples:
  dfsimage format image.ssd --title "Games"
"""

DKILL_EPILOG = """examples:
  dfsimage dkill beeb.mmb:300
"""

DRESTORE_EPILOG = """examples:
  dfsimage drestore --dlock -i 302 beeb.mmb
"""

DESTROY_USAGE = ('%(prog)s [global options] [destroy options] [image modify options] '
                 '[image file options] IMAGE FILES...')

DESTROY_EPILOG = """examples:
  dfsimage destroy image.ssd --ignore-access "A.*" "!BOOT"
"""

LOCK_USAGE = "%(prog)s [global options] [image modify options] [image file options] IMAGE FILES..."

ATTRIB_USAGE = ("%(prog)s [global options] [image modify options] [image file options] "
                "IMAGE ([file options] FILE)...")

ATTRIB_EPILOG = """examples:
  dfsimage attrib image.ssd --locked --load-addr=FF1900 "B.*"
"""

DIGEST_USAGE = "%(prog)s [global options] [digest options] [image file options] IMAGE FILE..."

DIGEST_EPILOG = """examples:
  dfsimage digest -a md5 image.ssd MY_PROG

  dfsimage digest -n image.ssd "*.*"

  dfsimage digest -nn --sector=0/0-0/1 image.ssd
"""


def cli(prog=None, argv=None):
    """Command line interface"""

    if prog is None:
        prog = __package__

    if len(sys.argv) > 1 and sys.argv[1] == '--trace':
        sys.argv.pop(1)
    else:
        sys.tracebacklimit = 0

    custom_format = CustomHelpFormat(max_help_position=40,
                                     gnu_style_long_options=True,
                                     formatter_class=MyHelpFormatter,
                                     flexi=True)

    custom_format_no_gnu = CustomHelpFormat(max_help_position=40,
                                            gnu_style_long_options=False,
                                            formatter_class=MyHelpFormatter,
                                            flexi=True)

    parser = argparse.ArgumentParser(prog=prog, usage=GLOBAL_USAGE,
                                     description=DESCRIPTION,
                                     formatter_class=custom_format,
                                     add_help=False)
    _add_global_options(parser, subparser=False)
    parser.add_argument('-h', '--help', action=_MyHelpAction, default=SUPPRESS,
                        help='Show this help message or command help message and exit.',
                        metavar="COMMAND")
    parser.add_argument('--help-options', action=_MyHelpOptionsAction, default=SUPPRESS,
                        help='Show detailed description of common options.')
    parser.add_argument('--help-format', action=_MyHelpFormatAction, default=SUPPRESS,
                        help='Show list of formatting keywords.')
    subparsers = parser.add_subparsers(title="commands", metavar="COMMAND",
                                       required="true")

    cmd = _add_subcommand(subparsers, prog, command="list",
                          aliases=["cat", "index"],
                          help="List files or disk image properties.",
                          usage=INDEX_USAGE,
                          epilog=INDEX_EPILOG,
                          format=custom_format)
    subcommands["cat"] = cmd
    subcommands["index"] = cmd
    _add_list_options(cmd, index=True)
    _add_image_options(cmd, existing=True, nargs='**')
    cmd.set_defaults(command=_list_command)

    cmd = _add_subcommand(subparsers, prog, command="create",
                          aliases=["modify"],
                          usage=CREATE_USAGE,
                          epilog=CREATE_EPILOG,
                          help="Create new floppy disk image or "
                               "modify existing image.",
                          format=custom_format)
    subcommands["modify"] = cmd
    _add_modify_options(cmd, "create")
    _add_image_options(cmd, existing=False, nargs=1)
    cmd.set_defaults(command=_create_command)

    cmd = _add_subcommand(subparsers, prog, command="backup",
                          aliases=["convert", "copy-disk"],
                          help="Copy (and convert) image or one floppy side of image.",
                          usage=BACKUP_USAGE,
                          epilog=BACKUP_EPILOG,
                          format=custom_format,
                          no_global=True)
    subcommands["convert"] = cmd
    subcommands["copy-disk"] = cmd
    required_args = cmd.add_argument_group("required arguments")
    required_args.group_usage = False
    _add_global_options(cmd)
    _add_command_options(cmd, "backup")
    _add_modify_options(cmd, "backup")
    _add_image_options(cmd, existing=False, nargs=None)
    _add_2images_arg(required_args, "backup")
    cmd.set_defaults(command=_backup_command)

    cmd = _add_subcommand(subparsers, prog, command="import",
                          help="Import files to floppy image.",
                          usage=IMPORT_USAGE,
                          epilog=IMPORT_EPILOG,
                          format=custom_format)
    _add_command_options(cmd, "import")
    _add_modify_options(cmd, "import")
    _add_image_options(cmd, existing=False, nargs=1)
    _add_import_file_options(cmd, "import")
    cmd.set_defaults(command=_import_command)

    cmd = _add_subcommand(subparsers, prog, command="export",
                          help="Export files from floppy image.",
                          usage=EXPORT_USAGE,
                          epilog=EXPORT_EPILOG,
                          format=custom_format,
                          no_global=True)
    required_args = cmd.add_argument_group('required arguments')
    required_args.group_usage = False
    _add_global_options(cmd)
    _add_command_options(cmd, "export")
    required_args.add_argument('-o', '--output',
                               help='Output directory or file name formatting string. '
                                    'Directory name must be terminated with path separator.',
                               required=True)
    _add_image_options(cmd, existing=True, nargs='**')
    cmd.set_defaults(command=_export_command)

    cmd = _add_subcommand(subparsers, prog, command="dump",
                          aliases=["read"],
                          help="Dump file or sectors contents.",
                          usage=DUMP_USAGE,
                          epilog=DUMP_EPILOG,
                          format=custom_format)
    subcommands["read"] = cmd
    _add_dump_options(cmd, "dump")
    _add_image_options(cmd, existing=True, nargs=1)
    cmd.add_argument("files", nargs="**", metavar="FILE", help="File to dump.", action='extend')
    cmd.set_defaults(command=_dump_command)

    cmd = _add_subcommand(subparsers, prog, command="build",
                          aliases=["write"],
                          help="Write data to file or sectors.",
                          usage=BUILD_USAGE,
                          epilog=BUILD_EPILOG,
                          format=custom_format)
    subcommands["write"] = cmd
    _add_dump_options(cmd, "build")
    _add_modify_options(cmd, "build")
    _add_image_options(cmd, existing=False, nargs=1)
    _add_import_file_options(cmd, "build")
    cmd.set_defaults(command=_build_command)

    cmd = _add_subcommand(subparsers, prog, command="copy-over",
                          help="Copy files from one image to another.",
                          usage=COPYOVER_USAGE,
                          epilog=COPYOVER_EPILOG,
                          format=custom_format,
                          no_global=True)
    required_args = cmd.add_argument_group("required arguments")
    required_args.group_usage = False
    _add_global_options(cmd)
    _add_command_options(cmd, "copy-over")
    _add_modify_options(cmd, "copy-over")
    _add_image_options(cmd, existing=False, nargs=None)
    _add_2images_arg(required_args, "copy-over")
    _add_files_arg(cmd, "copy")
    cmd.set_defaults(command=_copyover_command)

    cmd = _add_subcommand(subparsers, prog, command="format",
                          help="Format disk image removing all files.",
                          epilog=FORMAT_EPILOG,
                          format=custom_format)
    _add_modify_options(cmd, "format")
    _add_image_options(cmd, existing=False, nargs=1)
    cmd.set_defaults(command=_format_command)

    cmd = _add_subcommand(subparsers, prog, command="copy",
                          help="Copy file.",
                          format=custom_format)
    _add_command_options(cmd, "copy")
    _add_modify_options(cmd, "copy")
    _add_image_options(cmd, existing=True, nargs=1)
    _add_2file_arg(cmd, "copy")
    cmd.set_defaults(command=_copy_command)

    cmd = _add_subcommand(subparsers, prog, command="rename",
                          help="Rename file.",
                          format=custom_format)
    _add_command_options(cmd, "rename")
    _add_modify_options(cmd, "rename")
    _add_image_options(cmd, existing=True, nargs=1)
    _add_2file_arg(cmd, "rename")
    cmd.set_defaults(command=_rename_command)

    cmd = _add_subcommand(subparsers, prog, command="delete",
                          help="Delete file.",
                          format=custom_format)
    _add_command_options(cmd, "delete")
    _add_modify_options(cmd, "delete")
    _add_image_options(cmd, existing=True, nargs=1)
    cmd.add_argument('file', metavar='FILE', help='File to delete.', action='store')
    cmd.set_defaults(command=_delete_command)

    cmd = _add_subcommand(subparsers, prog, command="destroy",
                          help="Delete multiple files.",
                          usage=DESTROY_USAGE,
                          epilog=DESTROY_EPILOG,
                          format=custom_format)
    _add_command_options(cmd, "destroy")
    _add_modify_options(cmd, "destroy")
    _add_image_options(cmd, existing=True, nargs=1)
    _add_files_arg(cmd, "delete")
    cmd.set_defaults(command=_destroy_command)

    cmd = _add_subcommand(subparsers, prog, command="lock",
                          help="Lock files.",
                          usage=LOCK_USAGE,
                          format=custom_format)
    _add_command_options(cmd, "lock")
    _add_modify_options(cmd, "lock")
    _add_image_options(cmd, existing=True, nargs=1)
    _add_files_arg(cmd, "lock")
    cmd.set_defaults(command=_lock_command)

    cmd = _add_subcommand(subparsers, prog, command="unlock",
                          help="Unlock files.",
                          usage=LOCK_USAGE,
                          format=custom_format)
    _add_command_options(cmd, "unlock")
    _add_modify_options(cmd, "unlock")
    _add_image_options(cmd, existing=True, nargs=1)
    _add_files_arg(cmd, "unlock")
    cmd.set_defaults(command=_unlock_command)

    cmd = _add_subcommand(subparsers, prog, command="attrib",
                          help="Change existing file attributes.",
                          usage=ATTRIB_USAGE,
                          epilog=ATTRIB_EPILOG,
                          format=custom_format)
    _add_modify_options(cmd, "attrib")
    _add_image_options(cmd, existing=True, nargs=1)
    _add_import_file_options(cmd, "attrib")
    cmd.set_defaults(command=_attrib_command)

    cmd = _add_subcommand(subparsers, prog, command="digest",
                          help="Display digest (hash) of file or sectors contents",
                          usage=DIGEST_USAGE,
                          epilog=DIGEST_EPILOG,
                          format=custom_format)
    _add_dump_options(cmd, "digest")
    _add_image_options(cmd, existing=True, nargs=1)
    cmd.add_argument("files", nargs="**", metavar="FILE", help="File to process.", action='extend')
    cmd.set_defaults(command=_digest_command)

    cmd = _add_subcommand(subparsers, prog, command="validate",
                          help="Check disk for errors.",
                          format=custom_format)
    _add_image_options(cmd, True, nargs=1, command="validate")
    cmd.set_defaults(command=_validate_command)

    cmd = _add_subcommand(subparsers, prog, command="dkill",
                          help="Mark disk image as uninitialized in the MMB index.",
                          epilog=DKILL_EPILOG,
                          format=custom_format)
    _add_modify_options(cmd, "dkill")
    _add_image_options(cmd, True, nargs=1, command="dkill")
    cmd.set_defaults(command=_dkill_command)

    cmd = _add_subcommand(subparsers, prog, command="drestore",
                          help="Restore disk image marked previously as uninitialized.",
                          epilog=DRESTORE_EPILOG,
                          format=custom_format)
    _add_modify_options(cmd, "drestore")
    _add_image_options(cmd, True, nargs=1, command="drestore")
    cmd.set_defaults(command=_drestore_command)

    cmd = _add_subcommand(subparsers, prog, command="drecat",
                          help="Refresh MMB file catalog.",
                          format=custom_format)
    cmd.add_argument("images", metavar="MMB_FILE",
                     help="File to process.", action='append')
    _add_image_arg(cmd, None)
    cmd.set_defaults(command=_drecat_command)

    cmd = _add_subcommand(subparsers, prog, command="donboot",
                          help="Display or set images mounted in drives on boot.",
                          format=custom_format_no_gnu)
    cmd.add_argument("--set", dest='set_onboot', nargs=2, metavar=('DRIVE', 'IMAGE'),
                     type=int, help="Set new IMAGE to mount in DRIVE",
                     action='append', default=[])
    cmd.add_argument("images", metavar="MMB_FILE",
                     help="MMB file.", action='append')
    _add_image_arg(cmd, None)
    cmd.set_defaults(command=_donboot_command)

    cmd = _add_subcommand(subparsers, prog, command="create-mmb",
                          help="Create a new MMB file.",
                          format=custom_format)
    cmd.add_argument("images", metavar="MMB_FILE",
                     help="MMB file.", action='append')
    _add_image_arg(cmd, None)
    cmd.set_defaults(command=_create_mmb_command)

    cmd = argparse.ArgumentParser(prog=prog, usage="%(prog)s COMMAND [options]...", add_help=False,
                                  formatter_class=custom_format,
                                  description="Options help:")
    _add_global_options(cmd, True, True)
    group = _add_list_options(cmd, True, True)
    _add_command_options(cmd, "command", group)
    group.add_argument('-o', '--output',
                       help='Output directory or file name formatting string for export. '
                            'Directory name must be terminated with path separator.')
    _add_dump_options(cmd, "command", group)
    _add_modify_options(cmd, "template")
    _add_image_options(cmd, False, None, True)
    _add_import_file_options(cmd, "template")
    options_template.append(cmd)

    args = parser.parse_args(argv)
    if hasattr(args, "selected"):
        if args.from_image is None or len(args.from_image) == 0:
            parser.error("parameter FROM_IMAGE is required")
        if args.images is None or len(args.images) == 0:
            parser.error("parameter TO_IMAGE is required")
        if args.selected == "from":
            parser.error("excessive argument --from")
        if args.selected == "to":
            parser.error("excessive argument --to")
    elif args.images is None or len(args.images) == 0:
        parser.error("parameter IMAGE is required")

    if (args.tracks is not None or args.sides is not None or
            args.side is not None or args.linear is not None or
            args.index is not None or
            args.directory is not None or args.open_mode is not None):
        parser.error("image file options must be specified before image file name")

    args.command(args, parser)
