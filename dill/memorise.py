#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

"""
Module to show if an object has changed since it was memorised
"""

import io
import os
import sys
import gc

try:
    from collections.abc import MutableSequence
    import builtins
except ImportError:
    from collections import MutableSequence
    import __builtin__ as builtins
import types
# memo of objects indexed by id to a tuple (attributes, sequence items)
# attributes is a dict indexed by attribute name to attribute id
# sequence items is either a list of ids, of a dictionary of keys to ids
memo = {}
id_to_obj = {}
# types that
builtins_types = {str, list, dict, set, frozenset, int}


def get_attrs(obj):
    """
    Gets all the attributes of an object though its __dict__ or return None
    """
    if type(obj) in builtins_types \
       or type(obj) is type and obj in builtins_types:
        return None
    return obj.__dict__ if hasattr(obj, "__dict__") else None


def get_seq(obj):
    """
    Gets all the items in a sequence or return None
    """
    if type(obj) in (str, frozenset):
        return None
    elif isinstance(obj, dict):
        return obj
    elif isinstance(obj, MutableSequence):
        try:
            if len(obj):
                return list(iter(obj))
            else:
                return []
        except:
            return None
    return None


def get_attrs_id(obj):
    """
    Gets the ids of an object's attributes though its __dict__ or return None
    """
    if type(obj) in builtins_types \
       or type(obj) is type and obj in builtins_types:
        return None
    return {key: id(value) for key, value in obj.__dict__.items()} \
        if hasattr(obj, "__dict__") else None


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
    if isinstance(obj, dict):
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
        if isinstance(s, dict):
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


def cmp_seq(obj, seen):
    """
    Compares the contents of a container against the version stored in the
    memo. Return True if they compare equal, False otherwise.
    """
    obj_seq = memo[id(obj)][1]
    items = get_seq(obj)
    if items is not None:
        if len(items) != len(obj_seq):
            return False
        if isinstance(obj, dict):
            for key, item in items.items():
                key_id = id(key)
                item_id = id(item)
                if key_id not in obj_seq:
                    return False
                if item_id != obj_seq[key_id] \
                   or has_changed(key, seen, first=False) \
                   or has_changed(item, seen, first=False):
                    return False
        else:
            for i, j in zip(items, obj_seq):
                if id(i) != j or has_changed(i, seen, first=False):
                    return False
    return True


def cmp_attrs(obj, seen, fast=False):
    if not fast:
        changed_things = {}
    attrs = get_attrs(obj)
    if attrs is not None:
        for key in memo[id(obj)][0]:
            if key not in attrs:
                if fast:
                    return False
                changed_things[key] = None
        for key, o in attrs.items():
            if key not in memo[id(obj)][0] \
               or id(o) != memo[id(obj)][0][key] \
               or has_changed(o, seen, first=False):
                if fast:
                    return False
                changed_things[key] = o
    return True if fast else changed_things


def first_time_only(seen, obj):
    # ignore the _ variable, which only appears in interactive sessions
    if hasattr(builtins, "_"):
        memo[id(builtins)][0]["_"] = id(builtins._)
        memorise(builtins._, force=True)
        memo[id(builtins.__dict__)][1][id("_")] = id(builtins._)


def common_code(seen, obj):
    if obj is memo or obj is sys.modules or obj is sys.path_importer_cache \
       or obj is os.environ or obj is id_to_obj:
        return False
    if id(obj) in seen:
        return False
    seen.add(id(obj))


def has_changed(obj, seen=None, first=True):
    """
    Check an object against the memo. Returns True if the object has changed
    since memorisation, False otherwise.
    """
    seen = set() if seen is None else seen
    if first:
        first_time_only(seen, obj)
    r = common_code(seen, obj)
    if r is not None:
        return r
    if id(obj) not in memo:
        return True
    return not cmp_attrs(obj, seen, fast=True) or not cmp_seq(obj, seen)


def whats_changed(obj, seen=None, first=True):
    """
    Check an object against the memo. Returns a tuple in the form
    (attribute changes, container changed). Attribute changes is a dict of
    attribute name to attribute value. container changed is a boolean.
    """
    seen = set() if seen is None else seen
    if first:
        first_time_only(seen, obj)
    r = common_code(seen, obj)
    if r is not None:
        return ({}, False)
    if id(obj) not in memo:
        raise RuntimeError("Object not memorised " + str(obj))
    return cmp_attrs(obj, seen), not cmp_seq(obj, seen)

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

# memorise all already imported modules. This implies that this must be
# imported first for any changes to be recorded
for mod in sys.modules.values():
    memorise(mod, first=False)
release_gone()
