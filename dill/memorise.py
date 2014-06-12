#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

"""
Module to show if an object has changed since it was memorised
"""

import os
import sys
import numpy
try:
    import builtins
except ImportError:
    import __builtin__ as builtins

# memo of objects indexed by id to a tuple (attributes, sequence items)
# attributes is a dict indexed by attribute name to attribute id
# sequence items is either a list of ids, of a dictionary of keys to ids
memo = {}
id_to_obj = {}
# types that cannot have changing attributes
builtins_types = {str, list, dict, set, frozenset, int}


def get_attrs(obj):
    """
    Gets all the attributes of an object though its __dict__ or return None
    """
    if type(obj) in builtins_types \
       or type(obj) is type and obj in builtins_types:
        return None
    try:
        return obj.__dict__ if hasattr(obj, "__dict__") else None
    except:
        return None


def get_seq(obj, cashe={str: False, frozenset: False, list: True, set: True,
                        dict: True, tuple: True}):
    """
    Gets all the items in a sequence or return None
    """
    o_type = type(obj)
    if o_type in (numpy.ndarray, numpy.ma.core.MaskedConstant):
        if obj.shape and obj.size:
            return obj
        else:
            return []
    if o_type in cashe:
        if cashe[o_type]:
            if hasattr(obj, "copy"):
                return obj.copy()
            return obj
        return None
    elif hasattr(obj, "__contains__") and hasattr(obj, "__iter__") \
       and hasattr(obj, "__len__") and hasattr(o_type, "__contains__") \
       and hasattr(o_type, "__iter__") and hasattr(o_type, "__len__"):
        cashe[o_type] = True
        if hasattr(obj, "copy"):
            return obj.copy()
        return obj
    cashe[o_type] = None
    return None


def get_attrs_id(obj):
    """
    Gets the ids of an object's attributes though its __dict__ or return None
    """
    if type(obj) in builtins_types \
       or type(obj) is type and obj in builtins_types:
        return None
    try:
        return {key: id(value) for key, value in obj.__dict__.items()} \
            if hasattr(obj, "__dict__") else None
    except:
        return None


def get_seq_id(obj, done=None):
    """
    Gets the ids of the items in a sequence or return None
    """
    if done is not None:
        g = done
    else:
        g = get_seq(obj)
    if g is None:
        return None
    if hasattr(g, "items"):
        return {id(key): id(value) for key, value in g.items()}
    return [id(i) for i in g]


def memorise(obj, force=False, first=True):
    """
    Adds an object to the memo, and recursively adds all the objects
    attributes, and if it is a container, its items. Use force=True to update
    an object already in the memo. Updating is not recursively done.
    """
    if first:
        # add actions here
        pass
    if id(obj) in memo and not force:
        return
    if obj is memo or obj is id_to_obj:
        return
    g = get_attrs(obj)
    s = get_seq(obj)
    memo[id(obj)] = get_attrs_id(obj), get_seq_id(obj, done=s)
    id_to_obj[id(obj)] = obj
    if g is not None:
        for key, value in g.items():
            memorise(value, first=False)
    if s is not None:
        if hasattr(s, "items"):
            for key, item in s.items():
                memorise(key, first=False)
                memorise(item, first=False)
        else:
            for item in s:
                memorise(item, first=False)


def release_gone():
    rm = [id_ for id_, obj in id_to_obj.items() if sys.getrefcount(obj) < 4]
    for id_ in rm:
        del id_to_obj[id_]
        del memo[id_]


def whats_changed(obj, seen=None, first=True, simple=False):
    """
    Check an object against the memo. Returns a tuple in the form
    (attribute changes, container changed). Attribute changes is a dict of
    attribute name to attribute value. container changed is a boolean.
    """
    seen = {} if seen is None else seen
    if first:
        # ignore the _ variable, which only appears in interactive sessions
        if "_" in builtins.__dict__:
            del builtins._

    obj_id = id(obj)
    if obj_id not in memo:
        if simple:
            return True
        else:
            raise RuntimeError("Object not memorised " + str(obj))

    if obj_id in seen:
        if simple:
            return any(seen[obj_id])
        return seen[obj_id]

    if any(obj is i for i in (memo, sys.modules, sys.path_importer_cache,
           os.environ, id_to_obj)):
        seen[obj_id] = ({}, False)
        if simple:
            return False
        return seen[obj_id]

    seen[obj_id] = ({}, False)

    chngd = whats_changed
    id_ = id

    # compare attributes
    attrs = get_attrs(obj)
    if attrs is not None:
        obj_attrs = memo[id(obj)][0]
        obj_get = obj_attrs.get
        changed = {key: None for key in obj_attrs if key not in attrs}
        changed.update({key: o for key, o in attrs.items()
                        if id(o) != obj_get(key)
                        or chngd(o, seen, first=False, simple=True)})
    else:
        changed = {}

    # compare sequence
    items = get_seq(obj)
    if items is not None:
        seq_diff = False
        obj_seq = memo[id(obj)][1]
        if len(items) != len(obj_seq):
            seq_diff = True
        elif hasattr(obj, "items"):
            obj_get = obj_seq.get
            for key, item in items.items():
                if id_(item) != obj_get(id_(key)) \
                   or chngd(key, seen, first=False, simple=True) \
                   or chngd(item, seen, first=False, simple=True):
                    seq_diff = True
                    break
        else:
            for i, j in zip(items, obj_seq):
                if id_(i) != j or chngd(i, seen, first=False, simple=True):
                    seq_diff = True
                    break
    else:
        seq_diff = False
    seen[obj_id] = changed, seq_diff
    if simple:
        return changed or seq_diff
    return changed, seq_diff


def has_changed(*args, **kwargs):
    return whats_changed(*args, simple=True, **kwargs)

__import__ = __import__


def _imp(*args, **kwargs):
    """
    Replaces the default __import__, to allow a module to be memorised
    before the user can change it
    """
    mod = __import__(*args, **kwargs)
    memorise(mod)
    return mod

builtins.__import__ = _imp
if hasattr(builtins, "_"):
    del builtins._

# memorise all already imported modules. This implies that this must be
# imported first for any changes to be recorded
for mod in sys.modules.values():
    memorise(mod, first=False)
release_gone()
