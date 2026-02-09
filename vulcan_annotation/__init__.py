from .annotation import Annotation
from . import utilities

import os
from importlib.metadata import version
from importlib.resources import files

# Retrieve the package version
__version__ = version('vulcan_annotation')


def load_js():
    # files(__name__) locates the current package
    # .joinpath navigates into the 'js' subdirectory
    # .read_text() reads and decodes the file (default is utf-8)
    return files(__name__).joinpath('js', 'vulcan_annotation.js').read_text()


def load_va_dom():
    return files(__name__).joinpath('js', 'va_dom.js').read_text()