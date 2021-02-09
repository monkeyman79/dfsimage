#! /usr/bin/python3
"""Package entry script."""

import sys

if sys.version_info[0] != 3 or sys.version_info[1] < 8:
    raise ImportError("Module dfsimage requires Python version 3.8.")

# pylint: disable=wrong-import-position
import pathlib

if __name__ == '__main__':
    MY_DIR = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(MY_DIR.parent))

from dfsimage.cli import cli

cli()
