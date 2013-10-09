#!/usr/bin/env python

"""
Methods for detecting objects leading to pickling failures.
"""

from dill import _trace as trace

objects = {}
import objtypes as types # local import of dill.objtypes

def load_types(pickleable=True, unpickleable=True):
    """load pickleable and/or unpickleable types to dill.detect.types"""
    import objects as _objects # local import of dill.objects
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
    [types.__dict__.pop(obj) for obj in types.__dict__.keys() \
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
        except Exception, err:
            return err
    return dict(((attr, errors(getattr(obj,attr),depth-1,exact=exact)) \
           for attr in dir(obj) if not pickles(getattr(obj,attr),exact)))


# EOF
