import pytest
import dfsimage
import os
import io
import sys
from types import SimpleNamespace

GLOBAL = SimpleNamespace()

EMPTY_CATALOG = """ (00)
Drive 0             Option 0 (off)
Dir. :0.$           Lib. :0.$

"""

@pytest.fixture
def create_empty_image(tmpdir):
    GLOBAL.ssd_path = os.path.join(tmpdir, "image.ssd")
    with dfsimage.Image.create(GLOBAL.ssd_path):
        pass
    yield
    os.remove(GLOBAL.ssd_path)

@pytest.fixture
def empty_read_image(create_empty_image):
    image = dfsimage.Image.open(GLOBAL.ssd_path)
    yield image
    image.close()

def test_created_image_is_valid(empty_read_image):
    assert empty_read_image.sides[0].isvalid

def test_empty_image_catalog(empty_read_image):
    output = io.StringIO()
    empty_read_image.cat(file=output)
    assert output.getvalue() == EMPTY_CATALOG