# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

# -- Project information -----------------------------------------------------

project = 'dfsimage'
copyright = '2021 Tadek Kijkowski'
author = 'Tadek Kijkowski'

# The full version, including alpha/beta/rc tags
release = '0.9rc3'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'classic'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# autodoc_default_options = {
#     'special-members': '__init__'
# }

autodoc_typehints = 'description'

autodoc_member_order = 'bysource'

autodoc_type_aliases = {
    "PatternUnion": "dfsimage.pattern.PatternUnion",
    "dfsimage.enums.ListFormatUnion": "dfsimage.enums.ListFormatUnion"
}

napoleon_type_aliases = {
    "Image": "dfsimage.image.Image",
    "Side": "dfsimage.side.Size",
    "Entry": "dfsimage.entry.Entry",
    "ListFormat": "dfsimage.enums.ListFormat",
    "DigestMode": "dfsimage.enums.DigestMode",
    "SizeOption": "dfsimage.enums.SizeOption",
    "OpenMode": "dfsimage.enums.OpenMode",
    "WarnMode": "dfsimage.enums.WarnMode",
    "InfMode": "dfsimage.enums.InfMode",
    "TranslationMode": "dfsimage.enums.TranslationMode",
    "PatternUnion": "dfsimage.pattern.PatternUnion",
    "ListFormatUnion": "dfsimage.enums.ListFormatUnion"
}
