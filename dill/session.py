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

__all__ = [
    'FilterRules', 'dump_module', 'ipython_filter', 'load_module',
    'load_module_asdict', 'size_filter', 'EXCLUDE', 'INCLUDE',
    'dump_session', 'load_session'  # backward compatibility
]

import builtins
import pathlib
import random
import re
import sys
import tempfile
from statistics import mean
from types import SimpleNamespace

from dill import _dill, Pickler, Unpickler
from ._dill import (
    BuiltinMethodType, FunctionType, MethodType, ModuleType, TypeType,
    _import_module, _is_builtin_module, _is_imported_module, _main_module
)
from ._utils import FilterRules, RuleType
from .settings import settings

# Type hints.
from typing import Iterable, Optional, Union
from ._utils import Filter

EXCLUDE, INCLUDE = RuleType.EXCLUDE, RuleType.INCLUDE

SESSION_IMPORTED_AS_TYPES = (BuiltinMethodType, FunctionType, MethodType,
                             ModuleType, TypeType)

TEMPDIR = pathlib.PurePath(tempfile.gettempdir())

def _module_map():
    """get map of imported modules"""
    from collections import defaultdict
    modmap = SimpleNamespace(
        by_name=defaultdict(list),
        by_id=defaultdict(list),
        top_level={},
    )
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
    for name, obj in main_module.__dict__.items():
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

def _filter_objects(main, exclude, include, obj=None):
    rules = FilterRules(getattr(settings, 'dump_module', None))
    if exclude is not None:
        rules.update([(EXCLUDE, exclude)])
    if include is not None:
        rules.update([(INCLUDE, include)])

    namespace = rules.filter_namespace(main.__dict__, obj=obj)
    if namespace is main.__dict__:
        return main

    main = ModuleType(main.__name__)
    main.__dict__.update(namespace)
    return main

def dump_module(
    filename = str(TEMPDIR/'session.pkl'),
    main: Union[str, ModuleType] = '__main__',
    refimported: bool = False,
    exclude: Union[Filter, Iterable[Filter]] = None,
    include: Union[Filter, Iterable[Filter]] = None,
    **kwds
) -> None:
    """Pickle the current state of :py:mod:`__main__` or another module to a file.

    Save the interpreter session (the contents of the built-in module
    :py:mod:`__main__`) or the state of another module to a pickle file.  This
    can then be restored by calling the function :py:func:`load_module`.

    Runtime-created modules, like the ones constructed by
    :py:class:`~types.ModuleType`, can also be saved and restored thereafter.

    Parameters:
        filename: a path-like object or a writable stream.
        main: a module object or an importable module name.
        refimported: if `True`, all imported objects in the module's namespace
            are saved by reference. *Note:* this is different from the ``byref``
            option of other "dump" functions and is not affected by
            ``settings['byref']``.
        **kwds: extra keyword arguments passed to :py:class:`Pickler()`.

    Raises:
       :py:exc:`PicklingError`: if pickling fails.

    Examples:
        - Save current session state:

          >>> import dill
          >>> dill.dump_module()  # save state of __main__ to /tmp/session.pkl

        - Save the state of an imported/importable module:

          >>> import my_mod as m
          >>> m.var = 'new value'
          >>> dill.dump_module('my_mod_session.pkl', main='my_mod')

        - Save the state of a non-importable, runtime-created module:

          >>> from types import ModuleType
          >>> runtime = ModuleType('runtime')
          >>> runtime.food = ['bacon', 'eggs', 'spam']
          >>> runtime.process_food = m.process_food
          >>> dill.dump_module('runtime_session.pkl', main=runtime, refimported=True)

    *Changed in version 0.3.6:* the function ``dump_session()`` was renamed to
    ``dump_module()``.

    *Changed in version 0.3.6:* the parameter ``byref`` was renamed to
    ``refimported``.
    """
    if 'byref' in kwds:
        warnings.warn(
            "The parameter 'byref' was renamed to 'refimported', use this"
            " instead. Note: the underlying dill.Pickler do accept a 'byref'"
            " argument, but it has no effect on session saving.",
            PendingDeprecationWarning
        )
        if refimported:
            raise ValueError("both 'refimported' and 'byref' arguments were used.")
        refimported = kwds.pop('byref')
    from .settings import settings
    protocol = settings['protocol']
    if isinstance(main, str):
        main = _import_module(main)
    original_main = main
    if refimported:
        main = _stash_modules(main)
    main = _filter_objects(main, exclude, include, obj=original_main)
    if hasattr(filename, 'write'):
        file = filename
    else:
        file = open(filename, 'wb')
    try:
        pickler = Pickler(file, protocol, **kwds)
        pickler._original_main = main
        if refimported:
            main = _stash_modules(main)
        pickler._main = main     #FIXME: dill.settings are disabled
        pickler._byref = False   # disable pickling by name reference
        pickler._recurse = False # disable pickling recursion for globals
        pickler._session = True  # is best indicator of when pickling a session
        pickler._first_pass = True
        if main is not original_main:
            pickler._original_main = original_main
        pickler.dump(main)
    finally:
        if file is not filename:  # if newly opened file
            file.close()
    return

# Backward compatibility.
def dump_session(filename=str(TEMPDIR/'session.pkl'), main=None, byref=False, **kwds):
    warnings.warn("dump_session() was renamed to dump_module()", PendingDeprecationWarning)
    dump_module(filename, main, refimported=byref, **kwds)
dump_session.__doc__ = dump_module.__doc__

class _PeekableReader:
    """lightweight stream wrapper that implements peek()"""
    def __init__(self, stream):
        self.stream = stream
    def read(self, n):
        return self.stream.read(n)
    def readline(self):
        return self.stream.readline()
    def tell(self):
        return self.stream.tell()
    def close(self):
        return self.stream.close()
    def peek(self, n):
        stream = self.stream
        try:
            if hasattr(stream, 'flush'): stream.flush()
            position = stream.tell()
            stream.seek(position)  # assert seek() works before reading
            chunk = stream.read(n)
            stream.seek(position)
            return chunk
        except (AttributeError, OSError):
            raise NotImplementedError("stream is not peekable: %r", stream) from None

def _make_peekable(stream):
    """return stream as an object with a peek() method"""
    import io
    if hasattr(stream, 'peek'):
        return stream
    if not (hasattr(stream, 'tell') and hasattr(stream, 'seek')):
        try:
            return io.BufferedReader(stream)
        except Exception:
            pass
    return _PeekableReader(stream)

def _identify_module(file, main=None):
    """identify the session file's module name"""
    from pickletools import genops
    UNICODE = {'UNICODE', 'BINUNICODE', 'SHORT_BINUNICODE'}
    found_import = False
    try:
        for opcode, arg, pos in genops(file.peek(256)):
            if not found_import:
                if opcode.name in ('GLOBAL', 'SHORT_BINUNICODE') and \
                        arg.endswith('_import_module'):
                    found_import = True
            else:
                if opcode.name in UNICODE:
                    return arg
        else:
            raise UnpicklingError("reached STOP without finding main module")
    except (NotImplementedError, ValueError) as error:
        # ValueError occours when the end of the chunk is reached (without a STOP).
        if isinstance(error, NotImplementedError) and main is not None:
            # file is not peekable, but we have main.
            return None
        raise UnpicklingError("unable to identify main module") from error

def load_module(
    filename = str(TEMPDIR/'session.pkl'),
    main: Union[ModuleType, str] = None,
    **kwds
) -> Optional[ModuleType]:
    """Update :py:mod:`__main__` or another module with the state from the
    session file.

    Restore the interpreter session (the built-in module :py:mod:`__main__`) or
    the state of another module from a pickle file created by the function
    :py:func:`dump_module`.

    If loading the state of a (non-importable) runtime-created module, a version
    of this module may be passed as the argument ``main``.  Otherwise, a new
    module object is created with :py:class:`~types.ModuleType` and returned
    after it's updated.

    Parameters:
        filename: a path-like object or a readable stream.
        main: an importable module name or a module object.
        **kwds: extra keyword arguments passed to :py:class:`Unpickler()`.

    Raises:
        :py:exc:`UnpicklingError`: if unpickling fails.
        :py:exc:`ValueError`: if the ``main`` argument and the session file's
            module are incompatible.

    Returns:
        The restored module if it's different from :py:mod:`__main__` and
        wasn't passed as the ``main`` argument.

    Examples:
        - Load a saved session state:

          >>> import dill, sys
          >>> dill.load_module()  # updates __main__ from /tmp/session.pkl
          >>> restored_var
          'this variable was created/updated by load_module()'

        - Load the saved state of an importable module:

          >>> my_mod = dill.load_module('my_mod_session.pkl')
          >>> my_mod.var
          'new value'
          >>> my_mod in sys.modules.values()
          True

        - Load the saved state of a non-importable, runtime-created module:

          >>> runtime = dill.load_module('runtime_session.pkl')
          >>> runtime.process_food is my_mod.process_food  # was saved by reference
          True
          >>> runtime in sys.modules.values()
          False

        - Update the state of a non-importable, runtime-created module:

          >>> from types import ModuleType
          >>> runtime = ModuleType('runtime')
          >>> runtime.food = ['pizza', 'burger']
          >>> dill.load_module('runtime_session.pkl', main=runtime)
          >>> runtime.food
          ['bacon', 'eggs', 'spam']

    *Changed in version 0.3.6:* the function ``load_session()`` was renamed to
    ``load_module()``.

    See also:
        :py:func:`load_module_asdict` to load the contents of a saved session
        (from :py:mod:`__main__` or any importable module) into a dictionary.
    """
    main_arg = main
    if hasattr(filename, 'read'):
        file = filename
    else:
        file = open(filename, 'rb')
    try:
        file = _make_peekable(file)
        #FIXME: dill.settings are disabled
        unpickler = Unpickler(file, **kwds)
        unpickler._main = main
        unpickler._session = True
        pickle_main = _identify_module(file, main)

        # Resolve unpickler._main
        if main is None and pickle_main is not None:
            main = pickle_main
        if isinstance(main, str):
            if main.startswith('__runtime__.'):
                # Create runtime module to load the session into.
                main = ModuleType(main.partition('.')[-1])
            else:
                main = _import_module(main)
        if main is not None:
            if not isinstance(main, ModuleType):
                raise ValueError("%r is not a module" % main)
            unpickler._main = main
        else:
            main = unpickler._main

        # Check against the pickle's main.
        is_main_imported = _is_imported_module(main)
        if pickle_main is not None:
            is_runtime_mod = pickle_main.startswith('__runtime__.')
            if is_runtime_mod:
                pickle_main = pickle_main.partition('.')[-1]
            if is_runtime_mod and is_main_imported:
                raise ValueError(
                    "can't restore non-imported module %r into an imported one"
                    % pickle_main
                )
            if not is_runtime_mod and not is_main_imported:
                raise ValueError(
                    "can't restore imported module %r into a non-imported one"
                    % pickle_main
                )
            if main.__name__ != pickle_main:
                raise ValueError(
                    "can't restore module %r into module %r"
                    % (pickle_main, main.__name__)
                )

        # This is for find_class() to be able to locate it.
        if not is_main_imported:
            runtime_main = '__runtime__.%s' % main.__name__
            sys.modules[runtime_main] = main

        module = unpickler.load()
    finally:
        if not hasattr(filename, 'read'):  # if newly opened file
            file.close()
        try:
            del sys.modules[runtime_main]
        except (KeyError, NameError):
            pass
    assert module is main
    _restore_modules(unpickler, module)
    if module is _main_module or module is main_arg:
        return None
    else:
        return module

# Backward compatibility.
def load_session(filename=str(TEMPDIR/'session.pkl'), main=None, **kwds):
    warnings.warn("load_session() was renamed to load_module().", PendingDeprecationWarning)
    load_module(filename, main, **kwds)
load_session.__doc__ = load_module.__doc__

def load_module_asdict(
    filename = str(TEMPDIR/'session.pkl'),
    update: bool = False,
    **kwds
) -> dict:
    """
    Load the contents of a module from a session file into a dictionary.

    ``load_module_asdict()`` does the equivalent of this function::

        lambda filename: vars(load_module(filename)).copy()

    but without changing the original module.

    The loaded module's origin is stored in the ``__session__`` attribute.

    Parameters:
        filename: a path-like object or a readable stream
        update: if `True`, the dictionary is updated with the current state of
            the module before loading variables from the session file
        **kwds: extra keyword arguments passed to :py:class:`Unpickler()`

    Raises:
        :py:exc:`UnpicklingError`: if unpickling fails

    Returns:
        A copy of the restored module's dictionary.

    Note:
        If the ``update`` option is used, the original module will be loaded if
        it wasn't yet.

    Example:
        >>> import dill
        >>> alist = [1, 2, 3]
        >>> anum = 42
        >>> dill.dump_module()
        >>> anum = 0
        >>> new_var = 'spam'
        >>> main_vars = dill.load_module_asdict()
        >>> main_vars['__name__'], main_vars['__session__']
        ('__main__', '/tmp/session.pkl')
        >>> main_vars is globals()  # loaded objects don't reference current global variables
        False
        >>> main_vars['alist'] == alist
        True
        >>> main_vars['alist'] is alist  # was saved by value
        False
        >>> main_vars['anum'] == anum  # changed after the session was saved
        False
        >>> new_var in main_vars  # would be True if the option 'update' was set
        False
    """
    if 'main' in kwds:
        raise TypeError("'main' is an invalid keyword argument for load_module_asdict()")
    if hasattr(filename, 'read'):
        file = filename
    else:
        file = open(filename, 'rb')
    try:
        file = _make_peekable(file)
        main_name = _identify_module(file)
        old_main = sys.modules.get(main_name)
        main = ModuleType(main_name)
        if update:
            if old_main is None:
                old_main = _import_module(main_name)
            main.__dict__.update(old_main.__dict__)
        else:
            main.__builtins__ = builtins
        sys.modules[main_name] = main
        load_module(file, **kwds)
        main.__session__ = str(filename)
    finally:
        if not hasattr(filename, 'read'):  # if newly opened file
            file.close()
        try:
            if old_main is None:
                del sys.modules[main_name]
            else:
                sys.modules[main_name] = old_main
        except NameError:  # failed before setting old_main
            pass
    return main.__dict__


######################
#  Filter factories  #
######################

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
