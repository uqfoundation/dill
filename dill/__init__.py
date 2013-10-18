#!/usr/bin/env python
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#                              Mike McKerns, Caltech
#                        (C) 2008-2013  All Rights Reserved
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#

from __future__ import absolute_import

# get version numbers, license, and long description
try:
    from .info import this_version as __version__
    from .info import readme as __doc__, license as __license__
except ImportError:
    msg = """First run 'python setup.py build' to build dill."""
    raise ImportError(msg)

__author__ = 'Mike McKerns'

__doc__ = """
""" + __doc__

__license__ = """
""" + __license__

from .dill import dump, dumps, load, loads, dump_session, load_session, \
    Pickler, Unpickler, register, copy, pickle, pickles, HIGHEST_PROTOCOL, \
    PicklingError, UnpicklingError
from . import source, temp, detect
# load types and make types module available
from .detect import types as _types
detect.types = _types
del _types

def __extend():
    from .dill import _extend
    _extend()
    return
__extend(); del __extend

def license():
    """print license"""
    print (__license__)
    return

def citation():
    """print citation"""
    print (__doc__[-499:-140])
    return

del absolute_import

# end of file
