#!/usr/bin/env python

"""
Methods for detecting objects leading to pickling failures.
"""

from __future__ import absolute_import
from .pointers import parent, reference, refobject

from .dill import _trace as trace


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


# EOF
