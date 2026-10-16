# pylint: disable=redefined-outer-name, unused-argument
# pylint: disable=missing-module-docstring, missing-function-docstring
"""Tests for loading imperfect images (#11) and non-standard names (#12)."""
import io
import os

import pytest

import dfsimage
from dfsimage import simplewarn

SECTOR = 256


@pytest.fixture
def warnings(monkeypatch):
    """Capture warnings printed by simplewarn."""
    output = io.StringIO()
    monkeypatch.setattr(simplewarn, "stderr", output)
    return output


def make_image(path, files, tracks=80):
    with dfsimage.Image.create(path, tracks=tracks) as image:
        for name, data in files:
            image.add_file(name, data, load_addr=0x1900, exec_addr=0x8023)
    return path


def truncate(path, size):
    with open(path, "r+b") as file:
        file.truncate(size)


def patch(path, offset, data):
    with open(path, "r+b") as file:
        file.seek(offset)
        file.write(data)


# --- Issue #11: images that are shorter than they should be -------------

def test_partial_last_sector_is_padded(tmpdir, warnings):
    # Like Return to Eden / Dracula's Castle: the last sector is incomplete,
    # but all file data is present.
    path = make_image(os.path.join(tmpdir, "odd.ssd"),
                      [("GAME", b"G" * 1000), ("!BOOT", b"CHAIN\"GAME\"\r")])
    truncate(path, 4 * SECTOR + 1000 - 48)

    with dfsimage.Image.open(path) as image:
        assert image.isvalid
        assert image.get_entry("GAME").readall()[:952] == b"G" * 952

    assert "not a multiple of sector size" in warnings.getvalue()
    assert "truncated" not in warnings.getvalue()


def test_partial_last_sector_saved_as_full_sector(tmpdir, warnings):
    path = make_image(os.path.join(tmpdir, "odd.ssd"), [("GAME", b"G" * 1000)])
    truncate(path, 3 * SECTOR + 100)

    with dfsimage.Image.open(path, for_write=True) as image:
        image.sides[0].title = "FIXED"

    assert os.path.getsize(path) % SECTOR == 0
    with dfsimage.Image.open(path) as image:
        assert image.sides[0].title == "FIXED"


def test_non_standard_sector_count_with_short_image(tmpdir, warnings):
    # Like Dominium (293 sectors) / Boulder Dash Compendium (320 sectors):
    # the catalog is technically invalid, which used to make dfsimage demand
    # a full-size image, even though all file data is present.
    path = make_image(os.path.join(tmpdir, "odd_sectors.ssd"),
                      [("GAME", b"D" * 2000)])
    patch(path, SECTOR + 6, bytes([0x31, 0x25]))  # boot opt 3, 0x125 sectors
    truncate(path, 0x125 * SECTOR)

    with dfsimage.Image.open(path) as image:
        assert not image.isvalid
        assert image.get_entry("GAME").readall() == b"D" * 2000

    output = warnings.getvalue()
    assert "Invalid total number of sectors (293)" in output
    assert "truncated" not in output


def test_file_data_missing_reads_as_empty(tmpdir, warnings):
    path = make_image(os.path.join(tmpdir, "short.ssd"), [("GAME", b"T" * 5000)])
    truncate(path, 2 * SECTOR + 2048)

    with dfsimage.Image.open(path) as image:
        data = image.get_entry("GAME").readall()
        assert data[:2048] == b"T" * 2048
        assert data[2048:] == b"\xe5" * (5000 - 2048)

    assert "truncated" in warnings.getvalue()


def test_warn_none_silences_size_warnings(tmpdir, warnings):
    path = make_image(os.path.join(tmpdir, "short.ssd"), [("GAME", b"T" * 5000)])
    truncate(path, 2 * SECTOR + 2000)

    with dfsimage.Image.open(path, warn_mode=dfsimage.WarnMode.NONE):
        pass

    assert warnings.getvalue() == ""


def test_missing_catalog_is_still_an_error(tmpdir):
    path = make_image(os.path.join(tmpdir, "tiny.ssd"), [])
    truncate(path, SECTOR + 10)

    with pytest.raises(RuntimeError, match="too small"):
        dfsimage.Image.open(path)


# --- Issue #12: non-standard characters in file names -------------------

NAMES = ["P.\x0c\x15M", "\x18.\x18", "$.\x05", "$.\x7fDEL", "$.A\x00B"]


def make_names_image(path):
    with dfsimage.Image.create(path, allow_invalid_names=True) as image:
        for index, name in enumerate(NAMES):
            image.add_file(name, bytes([index]) * 100, load_addr=0x1900 + index,
                           locked=index % 2 == 0)
        image.add_file("$.NORMAL", b"N" * 300, load_addr=0xE00)
    return path


def snapshot(image):
    return sorted((entry.fullname_ascii, entry.load_address, entry.exec_address,
                   entry.locked, bytes(entry.readall()))
                  for entry in image.files)


def test_invalid_name_is_error_by_default(tmpdir):
    with dfsimage.Image.create(os.path.join(tmpdir, "new.ssd")) as image:
        with pytest.raises(ValueError, match="allow-invalid-names"):
            image.add_file("$.\x05", b"X")


def test_invalid_name_is_warning_when_allowed(tmpdir, warnings):
    path = os.path.join(tmpdir, "new.ssd")
    with dfsimage.Image.create(path, allow_invalid_names=True) as image:
        image.add_file("P.\x0c\x15M", b"X")

    assert warnings.getvalue().count("Invalid characters in file name") == 1
    assert "P.\\x0c\\x15M" in warnings.getvalue()

    with dfsimage.Image.open(path) as image:
        assert image.files.__next__().fullname_ascii == "P.\x0c\x15M"


def test_top_bit_characters_always_rejected(tmpdir):
    with dfsimage.Image.create(os.path.join(tmpdir, "new.ssd"),
                               allow_invalid_names=True) as image:
        with pytest.raises(ValueError):
            image.add_file("$.\x85BAD", b"X")


def test_round_trip_through_inf_files(tmpdir, warnings, monkeypatch):
    src_path = make_names_image(os.path.join(tmpdir, "src.ssd"))
    outdir = os.path.join(tmpdir, "files")
    os.mkdir(outdir)
    # Run from a different directory - inf files must be found regardless
    monkeypatch.chdir(tmpdir)

    with dfsimage.Image.open(src_path) as src:
        original = snapshot(src)
        src.export_files(outdir)

    data_files = [os.path.join(outdir, name) for name in os.listdir(outdir)
                  if not name.endswith(".inf")]

    with dfsimage.Image.create(os.path.join(tmpdir, "strict.ssd")) as dst:
        with pytest.raises(ValueError):
            dst.import_files(data_files, continue_on_error=False)

    dst_path = os.path.join(tmpdir, "rebuilt.ssd")
    with dfsimage.Image.create(dst_path, allow_invalid_names=True) as dst:
        assert dst.import_files(data_files, continue_on_error=False) == len(original)

    with dfsimage.Image.open(dst_path) as dst:
        assert snapshot(dst) == original


def test_copy_over_and_rename(tmpdir, warnings):
    src_path = make_names_image(os.path.join(tmpdir, "src.ssd"))
    dst_path = os.path.join(tmpdir, "copy.ssd")

    with dfsimage.Image.open(src_path) as src, \
            dfsimage.Image.create(dst_path, allow_invalid_names=True) as dst:
        dst.copy_over(src, "*.*", continue_on_error=False)
        dst.rename("$.NORMAL", "$.N\x01RMAL")

    with dfsimage.Image.open(dst_path) as dst:
        names = {entry.fullname_ascii for entry in dst.files}
    assert names == set(NAMES) | {"$.N\x01RMAL"}


def test_class_default(tmpdir, warnings, monkeypatch):
    monkeypatch.setattr(dfsimage.Image, "allow_invalid_names", True)
    with dfsimage.Image.create(os.path.join(tmpdir, "new.ssd")) as image:
        image.add_file("$.\x05", b"X")
