========
dfsimage
========

**BBC Micro Acorn DFS floppy disk image maintenance utility**

:Author: Tadeusz Kijkowski
:Version: 0.9

This package is a command-line utility and a Python module dedicated for
maintenance of BBC Micro disk image files. Those files usually have extensions
`.ssd` - for single sided disk image, or `.dsd` - for double sided disk image.

This package allows indexing contents of the disk images, importing files to and
exporting from the disk images and modifying disk images in place, such as
renaming files or changing disk title.

usage
=====

::

     dfsimage COMMAND IMAGE [options]...
     dfsimage --help [COMMAND]
     dfsimage --help-options
     dfsimage --help-format

command list
------------

.. |list| replace:: ``list``
.. |create| replace:: ``create``
.. |backup| replace:: ``backup``
.. |import| replace:: ``import``
.. |export| replace:: ``export``
.. |dump| replace:: ``dump``
.. |build| replace:: ``build``
.. |copy-over| replace:: ``copy-over``
.. |format| replace:: ``format``
.. |copy| replace:: ``copy``
.. |rename| replace:: ``rename``
.. |delete| replace:: ``delete``
.. |destroy| replace:: ``destroy``
.. |lock| replace:: ``lock``
.. |unlock| replace:: ``unlock``
.. |attrib| replace:: ``attrib``
.. |digest| replace:: ``digest``

|list|_ (``cat``, ``index``)
  List files or disk image properties.
|create|_ (``modify``)
  Create new floppy disk image or modify existing image.
|backup|_ (``convert``)
  Copy (and convert) image or one floppy side of image.
|import|_
  Import files to floppy image.
|export|_
  Export files from floppy image.
|dump|_ (``read``)
  Dump file or sectors contents
|build|_ (``write``)
  Write to file or sectors.
|copy-over|_
  Copy files from one image to another.
|format|_
  Format disk image removing all files.
|copy|_
  Copy single file.
|rename|_
  Rename single file.
|delete|_
  Delete single file.
|destroy|_
  Delete multiple files.
|lock|_
  Lock files.
|unlock|_
  Unlock files.
|attrib|_
  Change existing file attributes.
|digest|_
  Display digest (hash) of file or sectors contents

options
=======

global options
--------------

--warn=<none,first,all>
  Validation warnings display mode. (default: first)

  * ``none`` - Don't display validation warnings.
  * ``first`` - Display first warning and skip further validation
  * ``all`` - Display all validation warning. Some warnings may be redundant.

command-specific options
------------------------


-p, --pattern=PATTERN
  .. _pattern:

  File name or pattern. The `fnmatch` function is used for pattern matching.
  If the directory-matching part (e.g. ``'?.'``) is not present in the pattern,
  only files in the default directory are matched.

  * pattern ``'*'`` matches any string,
  * pattern ``'?'`` matches any single character,
  * pattern ``'[seq]'`` matches any character in `seq`,
  * pattern ``'[!seq]'`` matches any character not in `seq`.

-f, --list-format=<cat,info,raw,inf,json,xml,table,CUSTOM_FORMAT>
  .. _list-format:

  Listing format. (default: ``cat``)
  
  * ``raw`` - List file names
  * ``info`` - As displayed by ``*INFO`` command
  * ``inf`` - Format of ``.inf`` files
  * ``cat`` - As displayed by ``*CAT`` command
  * ``json`` - JSON
  * ``xml`` - XML
  * ``table`` - text table
  * *CUSTOM_FORMAT* - Formatting string - e.g. ``"{fullname:9} {size:06}"``.

  See `file properties`_ for list of keyword available for custom format.

--sort, --no-sort
  .. _sort:

  Sort files by name.

--header-format=<cat,table,CUSTOM_FORMAT>
  .. _header-format:

  Listing header format. (default: based of list format)

  * ``cat`` - As displayed by ``*CAT`` command.
  * ``table`` - text table
  * *CUSTOM_FORMAT* - Formatting string - e.g. ``"{title:12} {side}"``.

  See `disk side properties`_ for list of keywords available for custom format.

--footer-format=CUSTOM_FORMAT
  .. _footer-format:

  Listing footer format.
  See `disk side properties`_ for list of keywords available for custom format.

--image-header-format=CUSTOM_FORMAT
  .. _image-header-format:

  Listing header common for entire image file.

  * *CUSTOM_FORMAT* - Formatting string - e.g. ``"{image_basename} {tracks}"``.

  See `image file properties`_ for list of keywords available for custom format.

--image-footer-format=CUSTOM_FORMAT
  .. _image-footer-format:

  Image Listing footer format.
  See `image file properties`_ for list of keywords available for custom format.

--only-files
  .. _only-files:

  Include only files in listing - useful mainly for JSON, XML and table format

--only-sides
  .. _only-sides:

  Include only disk sides in listing - useful mainly for JSON, XML and table
  format

--only-images
  .. _only-images:

  Include only disk images in listing - useful mainly for JSON, XML and table
  format

-v, --verbose
  .. _verbose:

  Verbose mode - list copied files.

--create-dir, --no-create-dir
  .. _create-dir:

  Create output directories as needed. (default: False)

--translation=<standard,safe>
  .. _translation:

  Mode for translating dfs filename to host filename characters. (default:
  standard)

  * ``standard`` - replaces characters illegal on Windows with underscores.
  * ``safe`` - replaces all characters, other than digits and letters with
    underscores.

--include-drive-name
  .. _include-drive-name:

  Include drive name (i.e. :0. or :2.) in inf files created from double sided
  floppy images. The resulting inf files will be incompatible with most
  software. Use this option carefully.

--inf=<always,auto,never>
  .. _inf:

  Use of inf files.

  * ``always`` - always create `.inf` files, fail import if inf file doesn't
    exist.
  * ``auto`` - create `.inf` file if load or exec address is not 0, file is
    locked or filename cannot be directly translated to OS filename.
  * ``never`` - never create `.inf` files and ignore existing inf files on
    import.

--replace, --no-replace
  .. _replace:

  Allow replacing existing files. (default: False)

--ignore-access, --no-ignore-access
  .. _ignore-access:

  Allow deleting or replacing locked files. (default: False)

--silent
  .. _silent:

  Don't report error if the file to delete doesn't exist.

--preserve-attr, --no-preserve-attr
  .. _preserve-attr:

  Preserve ``'locked'`` attribute on copying. (default: False)

--continue, --no-continue
  .. _continue:

  Continue on non-fatal errors. (default: True)

-o, --output=OUTPUT
  .. _output:

  Output directory or file name formatting string for export.
  Directory name must be terminated with path separator.
  See `file properties`_ for list of keyword available for formatting string.

-f, --format=<raw,ascii,hex>
  .. _format-opt:

  Data format. (default: raw)

  * ``raw`` - read or write raw bytes.
  * ``ascii`` - escape all non-readable or non-ascii characters.
  * ``hex`` - hexadecimal dump.

--ellipsis, --no-ellipsis
  .. _ellipsis:

  Skip repeating lines in hex dump. (default: True)

--width=WIDTH
  .. _width:

  Bytes per line in hex dump.

-n, --name
  .. _name:

  Display each file or object name. Repeat for image name.

-m, --mode=<all,used,file,data>
  .. _mode:

  Digest mode for file:

  * ``all`` - include all attributes.
  * ``file`` - include load and execution addresses, but not access mode.
  * ``data`` - only file contents, don't include load and execution addresses
    or access mode.

  Digest mode for disk side:

  * ``all`` - include all sectors.
  * ``used`` - include used portions of catalog sectors and file sectors.
  * ``file`` - files sorted alphabetically; Load and exec addresses are included
    in the digest. File access mode and disk attributes are not included.

-a, --algorithm=ALGORITHM
  .. _algorithm:

  Digest algorithm, e.g. ``sha1``, ``sha256``, ``md5``

--sector=SECTOR
  .. _sector:

  Process sectors instead of files. Argument can be a range of sectors,
  with start and end separated by a dash. Physical sector address format is
  ``'track/sector'``.

--track=TRACK
  .. _track:

  Process tracks instead of files. Argument can be a range of tracks, with start
  and end separated by a dash.

--all
  .. _all:

  Process entire disk or disk side.

image modify options
--------------------

--title=TITLE
  Set disk title.
--new-title=TITLE
  Set disk title for newly created disk images.
--bootopt=<off,LOAD,RUN,EXEC>
  Set disk boot option.

  * off - No action.
  * LOAD - Execute `*LOAD $.!BOOT` command.
  * RUN - Execute `*RUN $.!BOOT` command.
  * EXEC - Execute `*EXEC $.!BOOT` command.

--sequence=SEQUENCE
  Set catalog sequence number. Sequence number is a Binary Coded Decimal value
  incremented by the Disk Filing System each time the disk catalog is modified.
--compact, --no-compact
  Coalesce fragmented free space on disk. Default is to compact disk if needed
  to make space for new file.
--shrink
  Shrink disk image file to minimum size by trimming unused sectors. Such image
  files are smaller, but cannot be memory-mapped and may have to be resized in
  flight by tools.
--expand
  Expand disk image file to maximum size.

image file options
--------------------

Image file options apply to the first following disk image file. Those options
must be specified before the corresponding image file name.

--new
  Create new image file. Fail if file already exists.
--existing
  Open existing image. Fail if file doesn't exist.
--always
  Create new image or open existing image,. This is the default.
-4<0>, -8<0>, --tracks=<80,40>
  Select between 80 and 40 track disks. Default for existing disk images is try
  to determine current disk format based on the image file size. Default for new
  disk images is 80 tracks.
-S, -D, --sides=<1,2>
  Select between single and double sided disk images. Default is to try to
  determine number of sides from disk extension and size: files with extension
  ``.dsd`` are open as double sided, other files are open as double sided based
  on their size. Default for new images is two sides for images with ``.dsd``
  extension and one side for all other.
-I, -L, --interleaved, --linear
  Select double sided disk data layout between interleaved and linear. The
  interleaved format is more common and more widely supported. In the
  interleaved format, track data of each floppy side is interleaved - side 1
  track 1, side 2 track 1, side 1 track 2 etc... Image files with extension
  ``.dsd`` are normally interleaved. Double sided image files with extension
  ``.ssd`` are normally linear (in this case ``s`` stands for "sequential").
  Double sided ``.ssd`` are distinguished from single sided by file size.
  For the theoretical 40 tracks, double sided ``.ssd`` files, you would have to
  manually specify ``-40``, ``-D`` and ``--linear``, because they cannot be
  reliably distinguished from 80 track single sided disk images.
-1, -2, --side=<1,2>
  Select disk side in case of double sided disks.
-d, --directory=DIRECTORY
  Default DFS directory.

file options
------------

File options apply to the first following file name. Those options override
values read from the inf file.

--load-address=ADDRESS
  Load address for the following file. Must be a hexadecimal number.
--exec-address=ADDRESS
  Exec address for the following file. Must be a hexadecimal number.
--locked, --no-locked
  Set locked attribute.
--dfs-name=NAME
  DFS name for the imported file.

commands
========

list
----

  List files or disk image properties.

  **synopsis**:

  .. parsed-literal::

    dfsimage list [`global options`_] [listing options] ([`image file options`_] IMAGE)...
    dfsimage cat [`global options`_] [listing options] ([`image file options`_] IMAGE)...
    dfsimage index [`global options`_] [listing options] ([`image file options`_] IMAGE)...

  **listing options**:

  .. parsed-literal::

    --pattern_
    --list-format_
    --sort_
    --header-format_
    --footer-format_
    --image-header-format_
    --image-footer-format_
    --only-files_
    --only-sides_
    --only-images_

  **examples**::

    dfsimage list image.ssd
    dfsimage list --image-header="Image {image_filename}" --header="Side {side}" --list-format="{fullname:12} {sha1}" img/*.dsd

create
------

  Create new floppy disk image or modify existing image.

  **synopsis**:

  .. parsed-literal::

    dfsimage create [`global options`_] [`image modify options`_] [`image file options`_] IMAGE
    dfsimage modify [`global options`_] [`image modify options`_] [`image file options`_] IMAGE

  **examples**::

    dfsimage create --new -D -L --title=Side1 --title=Side2 linear.img
    dfsimage modify --existing image.ssd --bootopt=EXEC

backup
------

  Copy (and convert) image or one floppy side of image.

  **synopsis**:

  .. parsed-literal::

    dfsimage backup [`global options`_] [`image modify options`_] --from [`image file options`_] FROM_IMAGE --to [`image file options`_] TO_IMAGE
    dfsimage convert [`global options`_] [`image modify options`_] --from [`image file options`_] FROM_IMAGE --to [`image file options`_] TO_IMAGE

  **examples**::

    dfsimage convert --from -D -L linear.img --to inter.dsd
    dfsimage backup --from -2 dual.dsd --to side2.ssd

import
------

  Import files to floppy image.

  **synopsis**:

  .. parsed-literal::

    dfsimage import [`global options`_] [import options] [`image modify options`_] [`image file options`_] IMAGE ([`file options`_] FILE)...

  **import options**:

  .. parsed-literal::

    --verbose_
    --inf_
    --replace_
    --ignore-access_
    --continue_

  **examples**::

    dfsimage import --new newfloppy.ssd --title="New floppy" files/*
    dfsimage import floppy.dsd --replace --ignore-access --load-addr=FF1900 --exec-addr=FF8023 --locked --dfs-name=':2.$.MY_PROG' my_prog.bin

export
------

  Export files from floppy image.

  **synopsis**:

  .. parsed-literal::

    dfsimage export [`global options`_] [export options] -o OUTPUT ([`image file options`_] IMAGE)...

  **required arguments**:

  .. parsed-literal::

    --output_

  **export options**:

  .. parsed-literal::

    --pattern_
    --verbose_
    --create-dir_
    --translation_
    --include-drive-name_
    --inf_
    --replace_
    --continue_

  **examples**::

    dfsimage export floppy.ssd -o floppy/ -p 'A.*'
    dfsimage export img/*.dsd --create-dir -o 'output/{image_basename}/{drive}.{fullname}'

dump
----

  Dump file or sectors contents.

  **synopsis**:

  .. parsed-literal::

    dfsimage dump [`global options`_] [dump options] [`image file options`_] IMAGE FILE...
    dfsimage read [`global options`_] [dump options] [`image file options`_] IMAGE FILE...

  **dump options**:

  .. parsed-literal::

    --format__
    --ellipsis_
    --width_
    --sector_
    --track_
    --all_

__ format-opt_

  **examples**::

    dfsimage dump image.ssd -f hex MY_PROG
    dfsimage dump image.ssd -f raw --sector=0-1 > cat-sectors.bin

build
-----

  Write data to file or sectors.

  **synopsis**:

  .. parsed-literal::

    dfsimage build [`global options`_] [build options] [`image modify options`_] [`image file options`_] IMAGE ([`file options`_] FILE)...
    dfsimage write [`global options`_] [build options] [`image modify options`_] [`image file options`_] IMAGE ([`file options`_] FILE)...

  **build options**:

  .. parsed-literal::

    --format__
    --replace_
    --ignore-access_
    --sector_
    --track_
    --all_

__ format-opt_

  **examples**::

    dfsimage list image.ssd | tr '\n' '\r' | dfsimage build image.ssd CATALOG
    dfsimage write image.ssd --sector=0-1 < cat-sectors.bin

copy-over
---------

  Copy files from one image to another.

  **synopsis**:

  .. parsed-literal::

    dfsimage copy-over [`global options`_] [copy-over options] [`image modify options`_] --from [`image file options`_] FROM_IMAGE --to [`image file options`_] TO_IMAGE FILES...

  **copy-over options**:

  .. parsed-literal::

    --verbose_
    --replace_
    --ignore-access_
    --preserve-attr_
    --continue_

  **examples**::

    dfsimage copy-over --from image.ssd --to another.ssd '?.BLAG*'

format
------

  Format disk image removing all files.

  **synopsis**:

  .. parsed-literal::

    dfsimage format [`global options`_] [`image modify options`_] [`image file options`_] IMAGE

  **examples**::

    dfsimage format image.ssd --title 'Games'

copy
----

  Copy single file.

  **synopsis**:

  .. parsed-literal::

    dfsimage copy [`global options`_] [copy options] [`image modify options`_] [`image file options`_] IMAGE FROM TO

  **copy options**:

  .. parsed-literal::

    --replace_
    --ignore-access_
    --preserve-attr_


rename
------

  Rename single file.

  **synopsis**:

  .. parsed-literal::

    dfsimage rename [`global options`_] [rename options] [`image modify options`_] [`image file options`_] IMAGE FROM TO

  **rename options**:

  .. parsed-literal::

    --replace_
    --ignore-access_

delete
------

  Delete single file.

  **synopsis**:

  .. parsed-literal::

    dfsimage delete [`global options`_] [delete options] [`image modify options`_] [`image file options`_] IMAGE FILE

  **delete options**:

  .. parsed-literal::

    --ignore-access_
    --silent_

destroy
-------

  Delete multiple files.

  **synopsis**:

  .. parsed-literal::

    dfsimage destroy [`global options`_] [destroy options] [`image modify options`_] [`image file options`_] IMAGE FILES...

  **destroy options**:

  .. parsed-literal::

    --ignore-access_

  **examples**::

    dfsimage destroy image.ssd --ignore-access 'A.*' '!BOOT'

lock
----

  Lock files.

  **synopsis**:

  .. parsed-literal::

    dfsimage lock [`global options`_] [`image modify options`_] [`image file options`_] IMAGE FILES...

unlock
------

  Unlock files.

  **synopsis**:

  .. parsed-literal::

    dfsimage unlock [`global options`_] [`image modify options`_] [`image file options`_] IMAGE FILES...

attrib
------

  Change existing file attributes.

  **synopsis**:

  .. parsed-literal::

    dfsimage attrib [`global options`_] [`image modify options`_] [`image file options`_] IMAGE ([`file options`_] FILE)...

  **examples**::

    dfsimage attrib image.ssd --locked --load-addr=FF1900 'B.*'

digest
------

  Display digest (hash) of file or sectors contents

  **synopsis**:

  .. parsed-literal::

    dfsimage digest [`global options`_] [digest options] [`image file options`_] IMAGE FILE...

  **digest options**:

  .. parsed-literal::

    --name_
    --mode_
    --algorithm_
    --sector_
    --track_
    --all_

  **examples**::

    dfsimage digest -a md5 image.ssd MY_PROG
    dfsimage digest -n image.ssd '*.*'
    dfsimage digest -nn --sector=0/0-0/1 image.ssd

formatting keyword arguments
============================

file properties
---------------

File properties can be used as keyword arguments in formatting string passed as
``--list-format`` argument for ``list`` command or ``--output`` argument for
``export`` command.

File properties are:

* ``index``                - File entry index.
* ``fullname``             - Full file name including directory name.
* ``load_addr``            - File load address.
* ``exec_addr``            - File execution address.
* ``access``               - File access mode - ``'L'`` if file is locked, empty
  otherwise.
* ``size``                 - File length in bytes.
* ``start_sector``         - Logical number of the first sector containing file
  data.
* ``end_sector``           - Logical number of the first sector after file data.
* ``sectors``              - Number of sectors occupied by file data
* ``sha1``                 - SHA1 digest of file data including load and
  execution addresses.
* ``sha1_data``            - SHA1 digest of file data not including load and
  execution addresses.
* ``sha1_all``             - SHA1 digest of file data including load and
  execution addresses and access mode.
* ``image_path``           - Full path of the floppy disk image file.
* ``image_filename``       - File name of the floppy disk image file.
* ``image_basename``       - File name of the floppy disk image file without
  extension.
* ``side``                 - Floppy disk side number - 1 or 2.
* ``directory``            - File directory name.
* ``filename``             - File name not including directory name.
* ``fullname_ascii``       - Full file name without translation of ASCII code
  0x60 to unicode Pound sign.
* ``displayname``          - File name as displayed by ``*CAT``
* ``locked``               - File access mode - True if file is locked.
* ``dir_str``              - Directory prefix as displayed by ``*CAT`` command.
* ``drive``                - Drive number according to DFS: 0 for side 1, 2 for
  side 2.
* ``head``                 - Head index: 0 for side 1, 1 for side 2.

disk side properties
--------------------

Floppy disk side properties can be used as keyword arguments in formatting
string passed as ``--header-format`` or ``--footer-format`` for ``list`` command.

Disk side properties are:

* ``side``                 - Floppy disk side number - 1 or 2.
* ``title``                - Floppy title string.
* ``sequence``             - Sequence number incremented each time the disk
  catalog is modified.
* ``opt_str``              - Boot option string - one of ``off``, ``LOAD``,
  ``RUN``, ``EXEC``.
* ``is_valid``             - Disk validation result.
* ``number_of_files``      - Number of files on floppy side.
* ``sectors``              - Number of sectors on disk reported by catalog
  sector.
* ``free_sectors``         - Number of free sectors.
* ``free_bytes``           - Number of free bytes.
* ``used_sectors``         - Number of used sectors
* ``max_free_blk_sectors`` - Number of sectors in largest continuous free block.
* ``max_free_blk``         - Size of largest continuous free block in bytes.
* ``sha1``                 - SHA1 digest of the entire floppy disk side surface.
* ``sha1_files``           - SHA1 digest of all files on the floppy disk side
  including their names and attributes.
* ``sha1_used``            - SHA1 digest of floppy disk side surface excluding
  unused areas.
* ``image_path``           - Full path of the floppy disk image file.
* ``image_filename``       - File name of the floppy disk image file.
* ``image_basename``       - File name of the floppy disk image file without
  extension.
* ``tracks``               - Number of tracks on the floppy disk side.
* ``drive``                - Drive number according to DFS: 0 for side 1, 2 for
  side 2.
* ``head``                 - Head index: 0 for side 1, 1 for side 2.
* ``end_offset``           - Last entry offset byte in catalog sector. Indicates
  number of files on the floppy disk image side.
* ``opt_byte``             - Options byte in catalog sectors. Contains among
  other boot option value.
* ``opt``                  - Boot options value.
* ``last_used_sector``     - Last used sector on floppy disk side.
* ``current_dir``          - Current directory - ``'$'`` by default.

image file properties
---------------------

Image file properties can be used as keyword arguments in formatting string
passed as ``--image-header-format`` or ``--image-footer-format`` for ``list``
command.

Image file properties are:

* ``image_path``           - Full path of the floppy disk image file.
* ``image_filename``       - File name of the floppy disk image file.
* ``image_basename``       - File name of the floppy disk image file without
  extension.
* ``number_of_sides``      - Number of floppy disk image sides.
* ``tracks``               - Number of tracks on each side.
* ``size``                 - Current disk image size.
* ``min_size``             - Minimum disk image size to include last used sector.
* ``max_size``             - Maximum disk image size.
* ``is_valid``             - True if disk validation succeeded.
* ``is_linear``            - True if floppy disk image file has linear layout is single sided or is double sided ssd file.
