========
dfsimage
========

**BBC Micro Acorn DFS floppy disk image maintenance utility**

This package contains a command-line utility and a Python module dedicated for
maintenance of **BBC Micro** disk image files. Those files usually have extensions
*.ssd* - for single sided disk image, or *.dsd* - for double sided disk image.

This package allows indexing contents of the disk images, importing files to and
exporting from the disk images, modifying disk images in place, such as
renaming files or changing disk title and transferring data between disk images.

The ``dfsimage`` module also supports *MMB* files. *MMB* files are containers for
large number of ``.ssd`` disk images, designed for storing disk images on a
MMC or SD card. All commands that work with *.ssd* FILES can be also used on a disk
image contained within an MMB file. Index of disk image within MMB file can be
either specified using `index`__ option, or appended to MMB file name, following
a colon character, e.g. ``beeb.mmb:12``. Commands |list|_, |dump|_ and |digest|_ can
take a range of disk images, e.g. ``beeb.mmb:10-20``. In that case command will be
applied to all *initialized* disk image in specified range.

There are few commands intended specially for MMB files, such as |donboot|_ or
|drecat|_.

__ index-opt_

usage
=====

.. code-block:: shell-session

  dfsimage COMMAND IMAGE [options]...
  dfsimage --help [COMMAND]
  dfsimage --help-options
  dfsimage --help-format

**examples**:

Index all floppy images with contents from the 'images' directory to 'index.json' file

.. code-block:: shell-session

  dfsimage index -f json images/*.ssd images/*.dsd > index.json

Covert a linear double sided image to a '.dsd' file

.. code-block:: shell-session

  dfsimage convert --from -D -L linear.img --to inter.dsd

Import all files from the 'files' directory to a new image 'games.ssd'

.. code-block:: shell-session

  dfsimage import --new games.ssd --title="GAMES" files/*

Export all files from the 'games.ssd' image to the 'files' directory

.. code-block:: shell-session

  dfsimage export beeb.mmb:12 -o files/

Index all floppy image contents from the 'images' directory to text table file

.. code-block:: shell-session

  dfsimage index --only-files -f table images/*.ssd images/*.dsd > files.csv

installation
============

At this point the package is not yet available in the PyPI repository, so 
it has to be build and installed manually:

Linux
-----

Make sure that pip and dependencies are installed.
If you are running Debian, Ubuntu or derived Linux distribution,
install the python3-pip package like this.

.. code-block:: shell-session

  ~$ sudo apt-get install python3-pip

Upgrade pip to latest version.

.. code-block:: shell-session

  ~$ python -m pip install --upgrade pip

Clone the repository

.. code-block:: shell-session

  ~/src$ git clone https://github.com/monkeyman79/dfsimage.git
  ~/src$ cd dfsimage

Build and install package

.. code-block:: shell-session

  ~/src/dfsimage$ python -m pip install .

Windows
-------

Before installing this package on a Windows machine, make sure that
both Python and Git are installed on your system.

* Python can be downloaded from here: https://www.python.org/downloads/
* Git for Windows can be downloaded from here: https://gitforwindows.org/

Make sure to add both Python and Git to your PATH when asked by the installer.

Execute steps below in either Command Prompt or Windows PowerShell.

.. code-block:: ps1con

  PS C:\Users\you> mkdir Documents\src
  PS C:\Users\you> cd Documents\src
  PS C:\Users\you\Documents\src> git clone "https://github.com/monkeyman79/dfsimage.git"
  PS C:\Users\you\Documents\src> cd dfsimage
  PS C:\Users\you\Documents\src\dfsimage> python -m pip install --user .

During installation, you may see the following warning message:

  **WARNING**: The script dfsimage.exe is installed in ``'C:\Users\you\AppData\Local\Packages\...\Scripts'``
  which is not on PATH.

  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.

This means that the ``'dfsimage'`` command will not be directly available. There are two options here:

* Always execute dfsimage via ``python -m dfsimage COMMAND...``
* Add the Scripts directory to your PATH variable

**Adding Scripts directory to your PATH variable**

We can combine powers of Python and PowerShell to automatically add your local
Scripts directory to PATH.
Execute the steps below in the Windows PowerShell:

.. code-block:: ps1con

  PS C:\Users\you> $USER_SITE = python -m site --user-site
  PS C:\Users\you> $USER_SCRIPTS = (Get-ChildItem (Split-Path -Path $USER_SITE -Parent) Scripts).FullName
  PS C:\Users\you> [Environment]::SetEnvironmentVariable("PATH",
  >> [Environment]::GetEnvironmentVariable("PATH", "User") + ";$USER_SCRIPTS", "User")

Now close your console window and open it again to make the change take effect.

command list
============

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
.. |validate| replace:: ``validate``
.. |create-mmb| replace:: ``create-mmb``
.. |dkill| replace:: ``dkill``
.. |drestore| replace:: ``drestore``
.. |drecat| replace:: ``drecat``
.. |donboot| replace:: ``donboot``

|list|_ (``cat``, ``index``)
  List files or disk image properties.
|create|_ (``modify``)
  Create new floppy disk image or modify existing image.
|backup|_ (``convert``, ``copy-disk``)
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
|validate|_
  Check disk for errors.
|create-mmb|_
  Create a new MMB file.
|dkill|_
  Mark disk image as uninitialized in the MMB index.
|drestore|_
  Restore disk image marked previously as uninitialized.
|drecat|_
  Refresh image titles in MMB file catalog.
|donboot|_
  Display or set images mounted in drives on boot.

options
=======

global options
--------------

``--warn={none,first,all}``
  Validation warnings display mode. (default: first)

  * ``none`` - Don't display validation warnings.
  * ``first`` - Display first warning and skip further validation
  * ``all`` - Display all validation warning. Some warnings may be redundant.

``-v, --verbose``
  Verbose mode - list copied files.
``-q, --quiet``
  Quiet mode - don't report successful operations.
``-s, --silent``
  Don't generate error if a file doesn't exist.
``--continue, --no-continue``
  Continue on non-fatal errors. (default: True)

common command options
------------------------

.. |pattern| replace:: ``-p, --pattern=PATTERN``
.. _pattern:

|pattern|
  File name or pattern. The `fnmatch` function is used for pattern matching.
  If the directory-matching part (e.g. ``'?.'``) is not present in the pattern,
  only files in the default directory are matched.

  * pattern ``'*'`` matches any string,
  * pattern ``'?'`` matches any single character,
  * pattern ``'[seq]'`` matches any character in `seq`,
  * pattern ``'[!seq]'`` matches any character not in `seq`.

  Commands: list_, export_

.. |inf| replace:: ``--inf={always,auto,never}``
.. _inf:

|inf|
  Use of inf files.

  * ``always`` - always create `.inf` files, fail import if inf file doesn't
    exist.
  * ``auto`` - create `.inf` file if either load or exec address is not 0, file
    is locked or filename cannot be directly translated to OS filename.
  * ``never`` - never create `.inf` files and ignore existing inf files on
    import.

  Commands: import_, export_

.. |replace| replace:: ``--replace, --no-replace``
.. _replace:

|replace|
  Allow replacing existing files. (default: False)

  Commands: import_, export_, build_, copy-over_, copy_, rename_

.. |ignore-access| replace:: ``--ignore-access, --no-ignore-access``
.. _ignore-access:

|ignore-access|
  Allow deleting or replacing locked files. (default: False)

  Commands: import_, build_, copy-over_, copy_, rename_, delete_, destroy_

.. |preserve-attr| replace:: ``--preserve-attr, --no-preserve-attr``
.. _preserve-attr:

|preserve-attr|
  Preserve ``'locked'`` attribute on copying. (default: False)

  Commands: copy-over_, copy_

.. |format-opt| replace:: ``-f, --format={raw,ascii,hex}``
.. _format-opt:

|format-opt|
  Data format. (default: raw)

  * ``raw`` - read or write raw bytes.
  * ``text`` - convert line endings to and from BBC's ``'\r'``
  * ``ascii`` - escape all non-readable or non-ascii characters.
  * ``hex`` - hexadecimal dump.

  Commands: dump_, build_

.. |sector| replace:: ``--sector=[TRACK/]SECTOR[-[TRACK/]SECTOR]``
.. _sector:

|sector|
  Process sectors instead of files. Argument can be a range of sectors,
  with start and end separated by a dash. Physical sector address format is
  ``'track/sector'``.

  Commands: dump_, build_, digest_

.. |track| replace:: ``--track=TRACK[-TRACK]``
.. _track:

|track|
  Process tracks instead of files. Argument can be a range of tracks, with start
  and end separated by a dash.

  Commands: dump_, build_, digest_

.. |all| replace:: ``--all``
.. _all:

|all|
  Process entire disk or disk side.

  Commands: dump_, build_, digest_

image modify options
--------------------

``--title=TITLE``
  Set disk title.
``--new-title=TITLE``
  Set disk title for newly created disk images.
``--bootopt={off,LOAD,RUN,EXEC}``
  Set disk boot option.

  * off - No action.
  * LOAD - Execute ``*LOAD $.!BOOT`` command.
  * RUN - Execute ``*RUN $.!BOOT`` command.
  * EXEC - Execute ``*EXEC $.!BOOT`` command.

``--sequence=SEQUENCE``
  Set catalog sequence number. Sequence number is a Binary Coded Decimal value
  incremented by the Disk Filing System each time the disk catalog is modified.
``--compact, --no-compact``
  Coalesce fragmented free space on disk. Default is to compact disk if needed
  to make space for new file.
``--shrink``
  Shrink disk image file to minimum size by trimming unused sectors. Such image
  files are smaller, but cannot be memory-mapped and may have to be resized in
  flight by tools.
``--expand``
  Expand disk image file to maximum size.

.. _dlock:

``--dlock``
  Set disk image locked flag in MMB index.

.. _dunlock:

``--dunlock``
  Reset disk image locked flag in MMB index.

image file options
--------------------

Image file options apply to the first following disk image file. Those options
must be specified before the corresponding image file name.

``--new``
  Create new image file. Fail if file already exists.
``--existing``
  Open existing image. Fail if file doesn't exist.
``--always``
  Create new image or open existing image,. This is the default.
``-4, -8, --tracks={80,40}``
  Select between 80 and 40 track disks. Default for existing disk images is try
  to determine current disk format based on the image file size. Default for new
  disk images is 80 tracks.
``-S, -D, --sides={1,2}``
  Select between single and double sided disk images. Default is to try to
  determine number of sides from disk extension and size: files with extension
  ``.dsd`` are open as double sided, other files are open as double sided based
  on their size. Default for new images is two sides for images with ``.dsd``
  extension and one side for all other.
``-I, -L, --interleaved, --linear``
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
``-1, -2, --side={1,2}``
  Select disk side for double sided disks.

.. _index-opt:

``-i, --index=INDEX``
  Select image index for MMB files. In case of double sided disks, index ``0``
  selects first side and index ``1`` selects second side. Alternatively index can be
  appended to the image file name separated by colon. For example
  ``my_disk.dsd:1`` or ``beeb.mmb:253``.
``-d, --directory=DIRECTORY``
  Default DFS directory.

file options
------------

File options apply to the first following file name. Those options override
values read from the inf file.

``--load-address=ADDRESS``
  Load address for the following file. Must be a hexadecimal number.
``--exec-address=ADDRESS``
  Exec address for the following file. Must be a hexadecimal number.
``--locked, --no-locked``
  Set locked attribute.
``--dfs-name=NAME``
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

**examples**:

.. code-block:: sh

  dfsimage cat image.ssd
  dfsimage list --image-header="Image {image_filename}" --header="Side {side}" --list-format="{fullname:12} {sha1}" img/*.dsd
  dfsimage index -f json images/*.ssd images/*.dsd > index.json

**listing options**:

|pattern|_

``-f, --list-format={cat,info,raw,inf,json,xml,table,CUSTOM_FORMAT}``
  Listing format. (default: ``cat``)
  
  * ``raw`` - List file names
  * ``info`` - As displayed by ``*INFO`` command
  * ``inf`` - Format of ``.inf`` files
  * ``cat`` - As displayed by ``*CAT`` command
  * ``json`` - JSON
  * ``xml`` - XML
  * ``dcat`` - As displayed by MMC ``*DCAT`` command
  * ``table`` - Text table. Columns are separated with ``'|'`` character.
  * *CUSTOM_FORMAT* - Formatting string - e.g. ``"{fullname:9} {size:06}"``.

  See `file properties`_ for list of keyword available for custom format.
``--sort, --no-sort``
  Sort files by name.
``--header-format={cat,table,CUSTOM_FORMAT}``
  Listing header format. (default: based of list format)

  * ``cat`` - As displayed by ``*CAT`` command.
  * ``table`` - text table
  * *CUSTOM_FORMAT* - Formatting string - e.g. ``"{title:12} {side}"``.

  See `disk side properties`_ for list of keywords available for custom format.
``--footer-format=CUSTOM_FORMAT``
  Listing footer format.
  See `disk side properties`_ for list of keywords available for custom format.
``--image-header-format=CUSTOM_FORMAT``
  Listing header common for entire image file.

  * *CUSTOM_FORMAT* - Formatting string - e.g. ``"{image_basename} {tracks}"``.

  See `image file properties`_ for list of keywords available for custom format.
``--image-footer-format=CUSTOM_FORMAT``
  Image Listing footer format.
  See `image file properties`_ for list of keywords available for custom format.
``--only-files``
  Include only files in listing - useful mainly for JSON, XML and table format
``--only-sides``
  Include only disk sides in listing - useful mainly for JSON, XML and table
  format
``--only-images``
  Include only disk images in listing - useful mainly for JSON, XML and table
  format

create
------

Create new floppy disk image or modify existing image.

**synopsis**:

.. parsed-literal::

  dfsimage create [`global options`_] [`image modify options`_] [`image file options`_] IMAGE
  dfsimage modify [`global options`_] [`image modify options`_] [`image file options`_] IMAGE

**examples**:

.. code-block:: sh

  dfsimage create --new -D -L --title=Side1 --title=Side2 linear.img
  dfsimage modify --existing image.ssd --bootopt=EXEC

backup
------

Copy (and convert) image or one floppy side of image.

**synopsis**:

.. parsed-literal::

  dfsimage backup [`global options`_] [`image modify options`_] --from [`image file options`_] FROM_IMAGE --to [`image file options`_] TO_IMAGE
  dfsimage convert [`global options`_] [`image modify options`_] --from [`image file options`_] FROM_IMAGE --to [`image file options`_] TO_IMAGE
  dfsimage copy-disk [`global options`_] [`image modify options`_] --from [`image file options`_] FROM_IMAGE --to [`image file options`_] TO_IMAGE

**examples**:

.. code-block:: sh

  dfsimage convert --from -D -L linear.img --to inter.dsd
  dfsimage backup --from -2 dual.dsd --to side2.ssd
  dfsimage copy-disk --from beeb.mmc:123 --to my_disk.ssd

import
------

Import files to floppy image.

**synopsis**:

.. parsed-literal::

  dfsimage import [`global options`_] [import options] [`image modify options`_] [`image file options`_] IMAGE ([`file options`_] FILE)...

**examples**:

.. code-block:: sh

  dfsimage import --new games.ssd --title="GAMES" files/*
  dfsimage import floppy.dsd --replace --ignore-access --load-addr=FF1900 --exec-addr=FF8023 --locked --dfs-name=':2.$.MY_PROG' my_prog.bin

**import options**:

|inf|_

|replace|_

|ignore-access|_

export
------

Export files from floppy image.

**synopsis**:

.. parsed-literal::

  dfsimage export [`global options`_] [export options] -o OUTPUT ([`image file options`_] IMAGE)...

**examples**:

.. code-block:: sh

  dfsimage export floppy.ssd -o floppy/ -p 'A.*'
  dfsimage export img/*.dsd --create-dir -o 'output/{image_basename}/{drive}.{fullname}'

**required arguments**:

``-o, --output=OUTPUT``
  Output directory or file name formatting string for export.
  Directory name must be terminated with path separator.
  See `file properties`_ for list of keyword available for formatting string.

**export options**:

|pattern|_

``--create-dir, --no-create-dir``
  Create output directories as needed. (default: False)
``--translation={standard,safe}``
  Mode for translating dfs filename to host filename characters. (default:
  standard)

  * ``standard`` - replaces characters illegal on Windows with underscores.
  * ``safe`` - replaces all characters, other than digits and letters with
    underscores.
``--include-drive-name``
  Include drive name (i.e. :0. or :2.) in inf files created from double sided
  floppy images. The resulting inf files will be incompatible with most
  software. Use this option carefully.

|inf|_

|replace|_

dump
----

Dump file or sectors contents.

**synopsis**:

.. parsed-literal::

  dfsimage dump [`global options`_] [dump options] [`image file options`_] IMAGE FILE...
  dfsimage read [`global options`_] [dump options] [`image file options`_] IMAGE FILE...

**examples**:

.. code-block:: sh

  dfsimage dump image.ssd -f hex MY_PROG
  dfsimage dump image.ssd -f raw --sector=0-1 > cat-sectors.bin

**dump options**:

|format-opt|_

``--ellipsis, --no-ellipsis``
  Skip repeating lines in the hex dump. (default: True)
``--width=WIDTH``
  Bytes per line in the hex dump.

|sector|_

|track|_

|all|_

build
-----

Write data to file or sectors.

**synopsis**:

.. parsed-literal::

  dfsimage build [`global options`_] [build options] [`image modify options`_] [`image file options`_] IMAGE ([`file options`_] FILE)...
  dfsimage write [`global options`_] [build options] [`image modify options`_] [`image file options`_] IMAGE ([`file options`_] FILE)...

**examples**:

.. code-block:: sh

  dfsimage list image.ssd | tr '\n' '\r' | dfsimage build image.ssd CATALOG
  dfsimage write image.ssd --sector=0-1 < cat-sectors.bin

**build options**:

|format-opt|_

|replace|_

|ignore-access|_

|sector|_

|track|_

|all|_

copy-over
---------

Copy files from one image to another.

**synopsis**:

.. parsed-literal::

  dfsimage copy-over [`global options`_] [copy-over options] [`image modify options`_] --from [`image file options`_] FROM_IMAGE --to [`image file options`_] TO_IMAGE FILES...

**examples**:

.. code-block:: sh

  dfsimage copy-over --from image.ssd --to another.ssd '?.BLAG*'

**copy-over options**:

|replace|_

|ignore-access|_

|preserve-attr|_

format
------

Format disk image removing all files.

**synopsis**:

.. parsed-literal::

  dfsimage format [`global options`_] [`image modify options`_] [`image file options`_] IMAGE

**examples**:

.. code-block:: sh

  dfsimage format image.ssd --title 'Games'

copy
----

Copy single file.

**synopsis**:

.. parsed-literal::

  dfsimage copy [`global options`_] [copy options] [`image modify options`_] [`image file options`_] IMAGE FROM TO

**copy options**:

|replace|_

|ignore-access|_

|preserve-attr|_

rename
------

Rename single file.

**synopsis**:

.. parsed-literal::

  dfsimage rename [`global options`_] [rename options] [`image modify options`_] [`image file options`_] IMAGE FROM TO

**rename options**:

|replace|_

|ignore-access|_

delete
------

Delete single file.

**synopsis**:

.. parsed-literal::

  dfsimage delete [`global options`_] [delete options] [`image modify options`_] [`image file options`_] IMAGE FILE

**delete options**:

|ignore-access|_

destroy
-------

Delete multiple files.

**synopsis**:

.. parsed-literal::

  dfsimage destroy [`global options`_] [destroy options] [`image modify options`_] [`image file options`_] IMAGE FILES...

**examples**:

.. code-block:: sh

  dfsimage destroy image.ssd --ignore-access 'A.*' '!BOOT'

**destroy options**:

|ignore-access|_

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

**examples**:

.. code-block:: sh

  dfsimage attrib image.ssd --locked --load-addr=FF1900 'B.*'

digest
------

Display digest (hash) of file or sectors contents

**synopsis**:

.. parsed-literal::

  dfsimage digest [`global options`_] [digest options] [`image file options`_] IMAGE FILE...

**examples**:

.. code-block:: sh

  dfsimage digest -a md5 image.ssd MY_PROG
  dfsimage digest -n image.ssd '*.*'
  dfsimage digest -nn --sector=0/0-0/1 image.ssd

**digest options**:

``-n, --name``
  Display each file or object name. Repeat for image name.

``-m, --mode={all,used,file,data}``
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

``-a, --algorithm=ALGORITHM``
  Digest algorithm, e.g. ``sha1``, ``sha256``, ``md5``

|sector|_

|track|_

|all|_

validate
--------

Check disk for errors. Runs the same cursory disk check that is executed before
any other disk operation.

**synopsis**:

.. parsed-literal::

  dfsimage validate [`global options`_] [`image file options`_] IMAGE

create-mmb
----------

Create a new MMB file.

**synopsis**:

.. parsed-literal::

  dfsimage create-mmb [`global options`_] MMB_FILE

dkill
-----

Mark disk image as uninitialized in the MMB index.

**synopsis**:

.. |dunlock| replace:: --dunlock

.. |index-opt| replace:: -i|--index=INDEX

.. parsed-literal::

  dfsimage dkill [`global options`_] [|dunlock|_] [|index-opt|_] IMAGE

**examples**:

.. code-block:: sh

  dfsimage dkill beeb.mmb:300

drestore
--------

Restore disk image marked previously as uninitialized.

**synopsis**:

.. |dlock| replace:: --dlock

.. parsed-literal::

  dfsimage drestore [`global options`_] [|dlock|_] [|index-opt|_] IMAGE

**examples**:

.. code-block:: sh

  dfsimage drestore --dlock -i 302 beeb.mmb

drecat
------

Refresh image titles in MMB file catalog.

**synopsis**:

.. parsed-literal::

  dfsimage drecat [`global options`_] MMB_FILE

donboot
-------

Display or set images mounted in drives on boot.

**synopsis**:

.. parsed-literal::

  dfsimage donboot [`global options`_] [--set DRIVE IMAGE]... MMB_FILE

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
* ``image_index``          - Index of the disk image in the MMB file.
* ``side``                 - Floppy disk side number - 1 or 2.
* ``image_displayname``    - File name of the floppy disk image with MMB index
  or double sided disk head number appended.
* ``image_index_or_head``  - Disk image index for MMB file or head number
  (0 or 1) for double sided disk.
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
string passed as ``--header-format`` or ``--footer-format`` for ``list``
command.

Disk side properties are:

* ``side``                 - Floppy disk side number - 1 or 2.
* ``title``                - Floppy title string.
* ``sequence``             - Sequence number incremented by the Acorn DFS each
  time the disk catalog is modified.
* ``opt_str``              - Boot option string - one of ``off``, ``LOAD``,
  ``RUN``, ``EXEC``.
* ``is_valid``             - Disk validation result.
* ``number_of_files``      - Number of files on the floppy disk side.
* ``sectors``              - Number of sectors on disk reported by the catalog.
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
* ``path``                 - Full path of the floppy disk image file.
* ``filename``             - File name of the floppy disk image file.
* ``basename``             - File name of the floppy disk image file without
  extension.
* ``index``                - Index of the disk image in the MMB file
* ``displayname``          - File name of the floppy disk image with MMB index
  or double sided disk head number appended.
* ``index_or_head``        - Disk image index for MMB file or head number
  (0 or 1) for double sided disk.
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
* ``locked``               - Image locked flag in the MMB catalog -
  True if image is locked.
* ``initialized``          - Image initialized flag in the MMB catalog -
  True if image is initialized.
* ``mmb_status``           - Image status in the MMB catalog:
  ``'L'`` if image is locked, ``'U'`` if image is uninitialized,
  ``'I'`` if status flag is invalid, empty string otherwise.
* ``mmb_status_byte``      - Raw MMB status byte value in the MMB catalog.

image file properties
---------------------

Image file properties can be used as keyword arguments in formatting string
passed as ``--image-header-format`` or ``--image-footer-format`` for ``list``
command.

Image file properties are:

* ``path``                 - Full path of the floppy disk image file.
* ``filename``             - File name of the floppy disk image file.
* ``basename``             - File name of the floppy disk image file without
  extension.
* ``index``                - Index of the disk image in the MMB file.
* ``displayname``          - File name of the floppy disk image with an MMB
  index appended.
* ``number_of_sides``      - Number of floppy disk image sides.
* ``tracks``               - Number of tracks on each side.
* ``size``                 - Current disk image size.
* ``min_size``             - Minimum disk image size to include last used sector.
* ``max_size``             - Maximum disk image size.
* ``is_valid``             - True if disk validation succeeded.
* ``is_linear``            - True if floppy disk image file has linear layout.
* ``locked``               - Image locked flag in the MMB catalog -
  True if image is locked.
* ``initialized``          - Image initialized flag in the MMB catalog -
  True if image is initialized.
* ``mmb_status``           - Image status in the MMB catalog:
  ``'L'`` if image is locked, ``'U'`` if image is uninitialized,
  ``'I'`` if status flag is invalid, empty string otherwise.
* ``mmb_status_byte``      - Raw MMB status byte value in the MMB catalog.
* ``sha1``                 - SHA1 digest of the entire disk image file.

development status
==================

The package is functionally complete, but lacks tests and Python module documentation.
