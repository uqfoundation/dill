#!/usr/bin/env python

"""
Methods for detecting objects leading to pickling failures.
"""

from __future__ import absolute_import
from .pointers import parent, reference, refobject

try:
    from imp import reload
except ImportError:
    pass

# put the objects in order, if possible
try:
    from collections import OrderedDict as odict
except ImportError:
    try:
        from ordereddict import OrderedDict as odict
    except ImportError:
        odict = dict
objects = odict()
# local import of dill.objects
from .dill import _trace as trace
from . import objects as _objects

objects.update(_objects.succeeds)
del _objects

# local import of dill.objtypes
from . import objtypes as types

def load_types(pickleable=True, unpickleable=True):
    """load pickleable and/or unpickleable types to dill.detect.types"""
    # local import of dill.objects
    from . import objects as _objects
    if pickleable:
        objects.update(_objects.succeeds)
    else:
        [objects.pop(obj,None) for obj in _objects.succeeds]
    if unpickleable:
        objects.update(_objects.failures)
    else:
        [objects.pop(obj,None) for obj in _objects.failures]
    objects.update(_objects.registered)
    del _objects
    # reset contents of types to 'empty'
    [types.__dict__.pop(obj) for obj in list(types.__dict__.keys()) \
                             if obj.find('Type') != -1]
    # add corresponding types from objects to types
    reload(types)


def badobjects(obj, depth=0, exact=False):
    """get objects that fail to pickle"""
    from dill import pickles
    if not depth:
        if pickles(obj,exact): return None
        return obj
    return dict(((attr, badobjects(getattr(obj,attr),depth-1,exact=exact)) \
           for attr in dir(obj) if not pickles(getattr(obj,attr),exact)))

def badtypes(obj, depth=0, exact=False):
    """get types for objects that fail to pickle"""
    from dill import pickles
    if not depth:
        if pickles(obj,exact): return None
        return type(obj)
    return dict(((attr, badtypes(getattr(obj,attr),depth-1,exact=exact)) \
           for attr in dir(obj) if not pickles(getattr(obj,attr),exact)))

def errors(obj, depth=0, exact=False):
    """get errors for objects that fail to pickle"""
    from dill import pickles, copy
    if not depth:
        try:
            pik = copy(obj)
            if exact:
                assert pik == obj, \
                    "Unpickling produces %s instead of %s" % (pik,obj)
            assert type(pik) == type(obj), \
                "Unpickling produces %s instead of %s" % (type(pik),type(obj))
            return None
        except Exception:
            import sys
            return sys.exc_info()[1]
    return dict(((attr, errors(getattr(obj,attr),depth-1,exact=exact)) \
           for attr in dir(obj) if not pickles(getattr(obj,attr),exact)))

del absolute_import
del odict


# EOF
