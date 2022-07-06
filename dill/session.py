#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Author: Leonardo Gama (@leogama)
# Copyright (c) 2008-2015 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
Pickle and restore the intepreter session.
"""

__all__ = ['dump_session', 'load_session', 'ipython_filter', 'ExcludeRules', 'EXCLUDE', 'INCLUDE']

import random
import re
import sys
from statistics import mean

from dill import _dill, Pickler, Unpickler
from ._dill import ModuleType, _import_module, _is_builtin_module, _main_module
from ._utils import AttrDict, ExcludeRules, Filter, RuleType
from .settings import settings

# Classes and abstract classes for type hints.
from io import BytesIO
from os import PathLike
from typing import Iterable, NoReturn, Union

EXCLUDE, INCLUDE = RuleType.EXCLUDE, RuleType.INCLUDE

SESSION_IMPORTED_AS_TYPES = tuple([Exception] + [getattr(_dill, name) for name in
        ('ModuleType', 'TypeType', 'FunctionType', 'MethodType', 'BuiltinMethodType')])

def _module_map():
    """get map of imported modules"""
    from collections import defaultdict
    modmap = AttrDict(by_name=defaultdict(list), by_id=defaultdict(list), top_level={})
    for modname, module in sys.modules.items():
        if not isinstance(module, ModuleType):
            continue
        if '.' not in modname:
            modmap.top_level[id(module)] = modname
        for objname, modobj in module.__dict__.items():
            modmap.by_name[objname].append((modobj, modname))
            modmap.by_id[id(modobj)].append((modobj, objname, modname))
    return modmap

def _lookup_module(modmap, name, obj, main_module):
    """lookup name or id of obj if module is imported"""
    for modobj, modname in modmap.by_name[name]:
        if modobj is obj and sys.modules[modname] is not main_module:
            return modname, name
    if isinstance(obj, SESSION_IMPORTED_AS_TYPES):
        for modobj, objname, modname in modmap.by_id[id(obj)]:
            if sys.modules[modname] is not main_module:
                return modname, objname
    return None, None

def _stash_modules(main_module):
    modmap = _module_map()
    newmod = ModuleType(main_module.__name__)

    imported = []
    imported_as = []
    imported_top_level = []  # keep separeted for backwards compatibility
    original = {}
    for name, obj in vars(main_module).items():
        if obj is main_module:
            original[name] = newmod  # self-reference
            continue

        # Avoid incorrectly matching a singleton value in another package (ex.: __doc__).
        if any(obj is singleton for singleton in (None, False, True)) or \
                isinstance(obj, ModuleType) and _is_builtin_module(obj):  # always saved by ref
            original[name] = obj
            continue

        source_module, objname = _lookup_module(modmap, name, obj, main_module)
        if source_module:
            if objname == name:
                imported.append((source_module, name))
            else:
                imported_as.append((source_module, objname, name))
        else:
            try:
                imported_top_level.append((modmap.top_level[id(obj)], name))
            except KeyError:
                original[name] = obj

    if len(original) < len(main_module.__dict__):
        newmod.__dict__.update(original)
        newmod.__dill_imported = imported
        newmod.__dill_imported_as = imported_as
        newmod.__dill_imported_top_level = imported_top_level
        return newmod
    else:
        return main_module

def _restore_modules(unpickler, main_module):
    try:
        for modname, name in main_module.__dict__.pop('__dill_imported'):
            main_module.__dict__[name] = unpickler.find_class(modname, name)
        for modname, objname, name in main_module.__dict__.pop('__dill_imported_as'):
            main_module.__dict__[name] = unpickler.find_class(modname, objname)
        for modname, name in main_module.__dict__.pop('__dill_imported_top_level'):
            main_module.__dict__[name] = __import__(modname)
    except KeyError:
        pass

def _filter_objects(main, exclude_extra, include_extra, obj=None):
    filters = ExcludeRules(getattr(settings, 'session_exclude', None))
    if exclude_extra is not None:
        filters.update([(EXCLUDE, exclude_extra)])
    if include_extra is not None:
        filters.update([(INCLUDE, include_extra)])

    namespace = filters.filter_namespace(vars(main), obj=obj)
    if namespace is vars(main):
        return main

    main = ModuleType(main.__name__)
    vars(main).update(namespace)
    return main

def dump_session(filename: Union[PathLike, BytesIO] = '/tmp/session.pkl',
                 main: Union[str, ModuleType] = '__main__',
                 byref: bool = False,
                 exclude: Union[Filter, Iterable[Filter]] = None,
                 include: Union[Filter, Iterable[Filter]] = None,
                 **kwds) -> NoReturn:
    """pickle the current state of __main__ to a file"""
    protocol = settings.protocol
    if isinstance(main, str):
        main = _import_module(main)
    original_main = main
    if byref:
        #NOTE: *must* run before _filter_objects()
        main = _stash_modules(main)
    main = _filter_objects(main, exclude, include, obj=original_main)
    if hasattr(filename, 'write'):
        f = filename
    else:
        f = open(filename, 'wb')
    try:
        pickler = Pickler(f, protocol, **kwds)
        pickler._main = main     #FIXME: dill.settings are disabled
        pickler._byref = False   # disable pickling by name reference
        pickler._recurse = False # disable pickling recursion for globals
        pickler._session = True  # is best indicator of when pickling a session
        pickler._first_pass = True
        if main is not original_main:
            pickler._original_main = original_main
        pickler.dump(main)
    finally:
        if f is not filename:  # If newly opened file
            f.close()
    return

def load_session(filename: Union[PathLike, BytesIO] = '/tmp/session.pkl',
                 main: ModuleType = None,
                 **kwds) -> NoReturn:
    """update the __main__ module with the state from the session file"""
    if main is None:
        main = _main_module
    if hasattr(filename, 'read'):
        f = filename
    else:
        f = open(filename, 'rb')
    try: #FIXME: dill.settings are disabled
        unpickler = Unpickler(f, **kwds)
        unpickler._main = main
        unpickler._session = True
        module = unpickler.load()
        unpickler._session = False
        main.__dict__.update(module.__dict__)
        _restore_modules(unpickler, main)
    finally:
        if f is not filename:  # If newly opened file
            f.close()
    return

import collections
import collections.abc
from sys import getsizeof

# Cover "true" collections from 'builtins', 'collections' and 'collections.abc'.
COLLECTION_TYPES = (
    list,
    tuple,
    collections.deque,
    collections.UserList,
    collections.abc.Mapping,
    collections.abc.Set,
)

def _estimate_size(obj, recursive=True):
    if recursive:
        return _estimate_size_recursively(obj, memo=set())
    try:
        return getsizeof(obj)
    except Exception:
        return 0

def _estimate_size_recursively(obj, memo):
    obj_id = id(obj)
    if obj_id in memo:
        return 0
    memo.add(obj_id)
    size = 0
    try:
        if isinstance(obj, ModuleType) and _is_builtin_module(obj):
            return 0
        size += getsizeof(obj)
        if hasattr(obj, '__dict__'):
            size += sum(_estimate_size(k, memo) + _estimate_size(v, memo) for k, v in obj.__dict__.items())
        if (isinstance(obj, str)   # common case shortcut
            or not isinstance(obj, collections.abc.Collection)  # general, single test
            or not isinstance(obj, COLLECTION_TYPES)  # specific, multiple tests
        ):
            return size
        if isinstance(obj, collections.ChainMap):  # collections.Mapping subtype
            size += sum(_estimate_size(mapping, memo) for mapping in obj.maps)
        elif len(obj) < 1000:
            if isinstance(obj, collections.abc.Mapping):
                size += sum(_estimate_size(k, memo) + _estimate_size(v, memo) for k, v in obj.items())
            else:
                size += sum(_estimate_size(item, memo) for item in obj)
        else:
            # Use random sample for large collections.
            sample = set(random.sample(range(len(obj)), k=100))
            if isinstance(obj, collections.abc.Mapping):
                samples_size = (_estimate_size(k, memo) + _estimate_size(v, memo)
                                for i, (k, v) in enumerate(obj.items()) if i in sample)
            else:
                samples_size = (_estimate_size(item, memo) for i, item in enumerate(obj) if i in sample)
            size += len(obj) * mean(filter(None, samples_size))
    except Exception:
        pass
    return size

def size_filter(limit, recursive=True):
    match = re.fullmatch(r'(\d+)\s*(B|[KMGT]i?B?)', limit, re.IGNORECASE)
    if not match:
        raise ValueError("invalid 'limit' value: %r" % limit)
    coeff, unit = match.groups()
    coeff, unit = int(coeff), unit.lower()
    if unit == 'b':
        limit = coeff
    else:
        base = 1024 if unit[1:2] == 'i' else 1000
        exponent = 'kmgt'.index(unit[0]) + 1
        limit = coeff * base**exponent
    def exclude_large(obj):
        return _estimate_size(obj.value, recursive) < limit
    return exclude_large


#############
#  IPython  #
#############

def ipython_filter(*, keep_input=True, keep_output=False):
    """filter factory for IPython sessions (can't be added to settings currently)

    Usage:
    >>> from dill.session import *
    >>> dump_session(exclude=[ipython_filter()])
    """
    if not __builtins__.get('__IPYTHON__'):
        # Return no-op filter if not in IPython.
        return (lambda x: False)

    from IPython import get_ipython
    ipython_shell = get_ipython()

    # Code snippet adapted from IPython.core.magics.namespace.who_ls()
    user_ns = ipython_shell.user_ns
    user_ns_hidden = ipython_shell.user_ns_hidden
    nonmatching = object()  # This can never be in user_ns
    interactive_vars = {x for x in user_ns if user_ns[x] is not user_ns_hidden.get(x, nonmatching)}

    # Input and output history.
    history_regex = []
    if keep_input:
        interactive_vars |= {'_ih', 'In', '_i', '_ii', '_iii'}
        history_regex.append(re.compile(r'_i\d+'))
    if keep_output:
        interactive_vars |= {'_oh', 'Out', '_', '__', '___'}
        history_regex.append(re.compile(r'_\d+'))

    def not_interactive_var(obj):
        if any(regex.fullmatch(obj.name) for regex in history_regex):
            return False
        return obj.name not in interactive_vars

    return not_interactive_var
