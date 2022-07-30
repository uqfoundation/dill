#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Author: Leonardo Gama (@leogama)
# Copyright (c) 2008-2015 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
Pickle and restore the intepreter session or a module's state.
"""

__all__ = [
    'dump_module', 'load_module', 'load_module_asdict', 'is_pickled_module',
    'dump_session', 'load_session' # backward compatibility
]

import contextlib
import re
import sys
import warnings

from dill import _dill, Pickler, Unpickler, UnpicklingError
from ._dill import (
    BuiltinMethodType, FunctionType, MethodType, ModuleType, TypeType,
    _import_module, _is_builtin_module, _is_imported_module, _main_module,
    _reverse_typemap, __builtin__,
)

# Type hints.
from typing import Optional, Union

import pathlib
import tempfile

TEMPDIR = pathlib.PurePath(tempfile.gettempdir())

class _PeekableReader:
    """lightweight readable stream wrapper that implements peek()"""
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

def _open(file, mode, *, peekable=False):
    """return a context manager with an opened file-like object"""
    import io
    attr = 'write' if 'w' in mode else 'read'
    was_open = hasattr(file, attr)
    if not was_open:
        file = open(file, mode)
    if attr == 'read' and peekable and not hasattr(file, 'peek'):
        # Try our best to return the stream as an object with a peek() method.
        if hasattr(file, 'tell') and hasattr(file, 'seek'):
            file = _PeekableReader(file)
        else:
            try:
                file = io.BufferedReader(file)
            except Exception:
                # Stream won't be peekable, but will fail gracefully in _identify_module().
                file = _PeekableReader(file)
    if was_open:  # should not close at exit
        return contextlib.nullcontext(file)
    elif type(file) == _PeekableReader:
        return contextlib.closing(file)
    else:
        return file

def _module_map():
    """get map of imported modules"""
    from collections import defaultdict
    from types import SimpleNamespace
    modmap = SimpleNamespace(
        by_name=defaultdict(list),
        by_id=defaultdict(list),
        top_level={},
    )
    for modname, module in sys.modules.items():
        if modname in ('__main__', '__mp_main__') or not isinstance(module, ModuleType):
            continue
        if '.' not in modname:
            modmap.top_level[id(module)] = modname
        for objname, modobj in module.__dict__.items():
            modmap.by_name[objname].append((modobj, modname))
            modmap.by_id[id(modobj)].append((modobj, objname, modname))
    return modmap

IMPORTED_AS_TYPES = (ModuleType, TypeType, FunctionType, MethodType, BuiltinMethodType)
if 'PyCapsuleType' in _reverse_typemap:
    IMPORTED_AS_TYPES += (_reverse_typemap['PyCapsuleType'],)

IMPORTED_AS_MODULES = [re.compile(x) for x in (
    'ctypes', 'typing', 'subprocess', 'threading',
    r'concurrent\.futures(\.\w+)?', r'multiprocessing(\.\w+)?'
)]

def _lookup_module(modmap, name, obj, main_module):
    """lookup name or id of obj if module is imported"""
    for modobj, modname in modmap.by_name[name]:
        if modobj is obj and sys.modules[modname] is not main_module:
            return modname, name
    __module__ = getattr(obj, '__module__', None)
    if isinstance(obj, IMPORTED_AS_TYPES) or (__module__ is not None
            and any(regex.fullmatch(__module__) for regex in IMPORTED_AS_MODULES)):
        for modobj, objname, modname in modmap.by_id[id(obj)]:
            if sys.modules[modname] is not main_module:
                return modname, objname
    return None, None

def _stash_modules(main_module):
    modmap = _module_map()
    newmod = ModuleType(main_module.__name__)

    imported = []
    imported_as = []
    imported_top_level = []  # keep separated for backward compatibility
    original = {}
    for name, obj in main_module.__dict__.items():
        if obj is main_module:
            original[name] = newmod  # self-reference
        elif obj is main_module.__dict__:
            original[name] = newmod.__dict__
        # Avoid incorrectly matching a singleton value in another package (ex.: __doc__).
        elif any(obj is singleton for singleton in (None, False, True)) \
                or isinstance(obj, ModuleType) and _is_builtin_module(obj):  # always saved by ref
            original[name] = obj
        else:
            source_module, objname = _lookup_module(modmap, name, obj, main_module)
            if source_module is not None:
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
        if getattr(newmod, '__loader__', None) is None and _is_imported_module(main_module):
            # Trick _is_imported_module() to force saving as an imported module.
            newmod.__loader__ = True  # will be discarded by save_module()
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

def dump_module(
    filename = str(TEMPDIR/'session.pkl'),
    module: Union[ModuleType, str] = None,
    *,
    refimported: bool = None,
    refonfail: bool = None,
    **kwds
) -> None:
    R"""Pickle the current state of :py:mod:`__main__` or another module to a file.

    Save the contents of :py:mod:`__main__` (e.g. from an interactive
    interpreter session), an imported module, or a module-type object (e.g.
    built with :py:class:`~types.ModuleType`), to a file. The pickled
    module can then be restored with the function :py:func:`load_module`.

    Parameters:
        filename: a path-like object or a writable stream.
        module: a module object or the name of an importable module. If `None`
            (the default), :py:mod:`__main__` is saved.
        refimported: if `True`, all objects identified as having been imported
            into the module's namespace are saved by reference. *Note:* this is
            similar but independent from ``dill.settings[`byref`]``, as
            ``refimported`` refers to virtually all imported objects, while
            ``byref`` only affects select objects.
        refonfail: if `True`, objects that fail to pickle by value will try to
            be saved by reference.  If this also fails, saving their parent
            objects by reference will be attempted recursively.  In the worst
            case scenario, the module itself may be saved by reference.  Note:
            The file-like object must be seekable and truncable with this
            option set.
        **kwds: extra keyword arguments passed to :py:class:`Pickler()`.

    Raises:
       :py:exc:`PicklingError`: if pickling fails.

    Examples:

        - Save current interpreter session state:

          >>> import dill
          >>> squared = lambda x: x*x
          >>> dill.dump_module() # save state of __main__ to /tmp/session.pkl

        - Save the state of an imported/importable module:

          >>> import dill
          >>> import pox
          >>> pox.plus_one = lambda x: x+1
          >>> dill.dump_module('pox_session.pkl', module=pox)

        - Save the state of a non-importable, module-type object:

          >>> import dill
          >>> from types import ModuleType
          >>> foo = ModuleType('foo')
          >>> foo.values = [1,2,3]
          >>> import math
          >>> foo.sin = math.sin
          >>> dill.dump_module('foo_session.pkl', module=foo, refimported=True)

        - Save the state of a module with unpickleable objects:

          >>> import dill
          >>> import os
          >>> os.altsep = '\\'
          >>> dill.dump_module('os_session.pkl', module=os)
          PicklingError: ...
          >>> dill.dump_module('os_session.pkl', module=os, refonfail=True)

        - Restore the state of the saved modules:

          >>> import dill
          >>> dill.load_module()
          >>> squared(2)
          4
          >>> pox = dill.load_module('pox_session.pkl')
          >>> pox.plus_one(1)
          2
          >>> foo = dill.load_module('foo_session.pkl')
          >>> [foo.sin(x) for x in foo.values]
          [0.8414709848078965, 0.9092974268256817, 0.1411200080598672]
          >>> os = dill.load_module('os_session.pkl')
          >>> print(os.altsep.join('path'))
          p\a\t\h

    *Changed in version 0.3.6:* Function ``dump_session()`` was renamed to
    ``dump_module()``.  Parameters ``main`` and ``byref`` were renamed to
    ``module`` and ``refimported``, respectively.

    Note:
        Currently, ``dill.settings['byref']`` and ``dill.settings['recurse']``
        don't apply to this function.
    """
    for old_par, par in [('main', 'module'), ('byref', 'refimported')]:
        if old_par in kwds:
            message = "The argument %r has been renamed %r" % (old_par, par)
            if old_par == 'byref':
                message += " to distinguish it from dill.settings['byref']"
            warnings.warn(message + ".", PendingDeprecationWarning)
            if locals()[par]:  # the defaults are None and False
                raise TypeError("both %r and %r arguments were used" % (par, old_par))
    refimported = kwds.pop('byref', refimported)
    module = kwds.pop('main', module)

    from .settings import settings
    protocol = settings['protocol']
    if refimported is None:
        refimported = settings['dump_module']['refimported']
    if refonfail is None:
        refonfail = settings['dump_module']['refonfail']
    main = module
    if main is None:
        main = _main_module
    elif isinstance(main, str):
        main = _import_module(main)
    if not isinstance(main, ModuleType):
        raise TypeError("%r is not a module" % main)
    original_main = main
    if refimported:
        main = _stash_modules(main)
    with _open(filename, 'wb') as file:
        pickler = Pickler(file, protocol, **kwds)
        if main is not original_main:
            pickler._original_main = original_main
        pickler._main = main     #FIXME: dill.settings are disabled
        pickler._byref = False   # disable pickling by name reference
        pickler._recurse = False # disable pickling recursion for globals
        pickler._session = True  # is best indicator of when pickling a session
        pickler._first_pass = True
        if refonfail:
            pickler._refonfail = True  # False by default
            pickler._file_seek = getattr(file, 'seek', None)
            pickler._file_truncate = getattr(file, 'truncate', None)
            if hasattr(file, 'seekable') and not file.seekable():
                pickler._file_seek = None
            if pickler._file_seek is None or pickler._file_truncate is None:
                raise TypeError("file must have 'tell', 'seek' and 'truncate'"
                                " attributes if the 'refonfail' option is set.")
        pickler.dump(main)
    return

# Backward compatibility.
def dump_session(filename=str(TEMPDIR/'session.pkl'), main=None, byref=False, **kwds):
    warnings.warn("dump_session() has been renamed dump_module()", PendingDeprecationWarning)
    dump_module(filename, module=main, refimported=byref, **kwds)
dump_session.__doc__ = dump_module.__doc__

def _identify_module(file, main=None):
    """identify the name of the module stored in the given file-type object"""
    import pickletools
    NEUTRAL = {'PROTO', 'FRAME', 'PUT', 'BINPUT', 'MEMOIZE', 'MARK', 'STACK_GLOBAL'}
    opcodes = ((opcode.name, arg) for opcode, arg, pos in pickletools.genops(file.peek(256))
               if opcode.name not in NEUTRAL)
    try:
        opcode, arg = next(opcodes)
        if (opcode, arg) == ('SHORT_BINUNICODE', 'dill._dill'):
            # The file uses STACK_GLOBAL instead of GLOBAL.
            opcode, arg = next(opcodes)
        if not (opcode in ('SHORT_BINUNICODE', 'GLOBAL') and arg.split()[-1] == '_import_module'):
            raise ValueError
        opcode, arg = next(opcodes)
        if not opcode in ('SHORT_BINUNICODE', 'BINUNICODE', 'UNICODE'):
            raise ValueError
        module_name = arg
        if not (
            next(opcodes)[0] in ('TUPLE1', 'TUPLE') and
            next(opcodes)[0] == 'REDUCE' and
            next(opcodes)[0] in ('EMPTY_DICT', 'DICT')
        ):
            raise ValueError
        return module_name
    except StopIteration:
        raise UnpicklingError("reached STOP without finding module") from None
    except (NotImplementedError, ValueError) as error:
        # ValueError occours when the end of the chunk is reached (without a STOP).
        if isinstance(error, NotImplementedError) and main is not None:
            # file is not peekable, but we have main.
            return None
        raise UnpicklingError("unable to identify module") from error

def is_pickled_module(filename, importable: bool = True) -> bool:
    """Check if a file is a module state pickle file.

    Parameters:
        filename: a path-like object or a readable stream.
        importable: expected kind of the file's saved module. Use `True` for
            importable modules (the default) or `False` for module-type objects.

    Returns:
        `True` if the pickle file at ``filename`` was generated with
        :py:func:`dump_module` **AND** the module whose state is saved in it is
        of the kind specified by the ``importable`` argument. `False` otherwise.
    """
    with _open(filename, 'rb', peekable=True) as file:
        try:
            pickle_main = _identify_module(file)
        except UnpicklingError:
            return False
        else:
            is_runtime_mod = pickle_main.startswith('__runtime__.')
            return importable ^ is_runtime_mod

def load_module(
    filename = str(TEMPDIR/'session.pkl'),
    module: Union[ModuleType, str] = None,
    **kwds
) -> Optional[ModuleType]:
    """Update the selected module (default is :py:mod:`__main__`) with
    the state saved at ``filename``.

    Restore a module to the state saved with :py:func:`dump_module`. The
    saved module can be :py:mod:`__main__` (e.g. an interpreter session),
    an imported module, or a module-type object (e.g. created with
    :py:class:`~types.ModuleType`).

    When restoring the state of a non-importable module-type object, the
    current instance of this module may be passed as the argument ``module``.
    Otherwise, a new instance is created with :py:class:`~types.ModuleType`
    and returned.

    Parameters:
        filename: a path-like object or a readable stream.
        module: a module object or the name of an importable module;
            the module name and kind (i.e. imported or non-imported) must
            match the name and kind of the module stored at ``filename``.
        **kwds: extra keyword arguments passed to :py:class:`Unpickler()`.

    Raises:
        :py:exc:`UnpicklingError`: if unpickling fails.
        :py:exc:`ValueError`: if the argument ``module`` and module saved
            at ``filename`` are incompatible.

    Returns:
        A module object, if the saved module is not :py:mod:`__main__` or
        a module instance wasn't provided with the argument ``module``.

    Passing an argument to ``module`` forces `dill` to verify that the module
    being loaded is compatible with the argument value.  Additionally, if the
    argument is a module (instead of a module name), it supresses the return
    value. Each case and behavior is exemplified below:

        1. `module`: ``None`` --- This call loads a previously saved state of
        the module ``math`` and returns this at the end:

            >>> import dill
            >>> # load module -> restore state -> return module
            >>> dill.load_module('math_session.pkl')
            <module 'math' (built-in)>

        2. `module`: ``str`` --- Passing the module name does the same as above,
        but also verifies that the module loaded, restored and returned is
        indeed ``math``:

            >>> import dill
            >>> # load module -> check name/kind -> restore state -> return module
            >>> dill.load_module('math_session.pkl', module='math')
            <module 'math' (built-in)>
            >>> dill.load_module('math_session.pkl', module='cmath')
            ValueError: can't update module 'cmath' with the saved state of module 'math'

        3. `module`: ``ModuleType`` --- Passing the module itself instead of its
        name have the additional effect of supressing the return value (and the
        module is already loaded at this point):

            >>> import dill
            >>> import math
            >>> # check name/kind -> restore state -> return None
            >>> dill.load_module('math_session.pkl', module=math)

    For imported modules, the return value is meant as a convenience, so that
    the function call can substitute an ``import`` statement.  Therefore these
    statements:

        >>> import dill
        >>> math2 = dill.load_module('math_session.pkl', module='math')

    are equivalent to these:

        >>> import dill
        >>> import math as math2
        >>> dill.load_module('math_session.pkl', module=math2)

    Note that, in both cases, ``math2`` is just a reference to
    ``sys.modules['math']``:

        >>> import math
        >>> import sys
        >>> math is math2 is sys.modules['math']
        True

    Examples:

        - Save the state of some modules:

          >>> import dill
          >>> squared = lambda x: x*x
          >>> dill.dump_module() # save state of __main__ to /tmp/session.pkl
          >>>
          >>> import pox # an imported module
          >>> pox.plus_one = lambda x: x+1
          >>> dill.dump_module('pox_session.pkl', module=pox)
          >>>
          >>> from types import ModuleType
          >>> foo = ModuleType('foo') # a module-type object
          >>> foo.values = [1,2,3]
          >>> import math
          >>> foo.sin = math.sin
          >>> dill.dump_module('foo_session.pkl', module=foo, refimported=True)

        - Restore the state of the interpreter:

          >>> import dill
          >>> dill.load_module() # updates __main__ from /tmp/session.pkl
          >>> squared(2)
          4

        - Load the saved state of an importable module:

          >>> import dill
          >>> pox = dill.load_module('pox_session.pkl')
          >>> pox.plus_one(1)
          2
          >>> import sys
          >>> pox in sys.modules.values()
          True

        - Load the saved state of a non-importable module-type object:

          >>> import dill
          >>> foo = dill.load_module('foo_session.pkl')
          >>> [foo.sin(x) for x in foo.values]
          [0.8414709848078965, 0.9092974268256817, 0.1411200080598672]
          >>> import math
          >>> foo.sin is math.sin # foo.sin was saved by reference
          True
          >>> import sys
          >>> foo in sys.modules.values()
          False

        - Update the state of a non-importable module-type object:

          >>> import dill
          >>> from types import ModuleType
          >>> foo = ModuleType('foo')
          >>> foo.values = ['a','b']
          >>> foo.sin = lambda x: x*x
          >>> dill.load_module('foo_session.pkl', module=foo)
          >>> [foo.sin(x) for x in foo.values]
          [0.8414709848078965, 0.9092974268256817, 0.1411200080598672]

    *Changed in version 0.3.6:* Function ``load_session()`` was renamed to
    ``load_module()``. Parameter ``main`` was renamed to ``module``.

    See also:
        :py:func:`load_module_asdict` to load the contents of module saved
        with :py:func:`dump_module` into a dictionary.
    """
    if 'main' in kwds:
        warnings.warn(
            "The argument 'main' has been renamed 'module'.",
            PendingDeprecationWarning
        )
        if module is not None:
            raise TypeError("both 'module' and 'main' arguments were used")
        module = kwds.pop('main')
    main = module
    with _open(filename, 'rb', peekable=True) as file:
        #FIXME: dill.settings are disabled
        unpickler = Unpickler(file, **kwds)
        unpickler._session = True

        # Resolve unpickler._main
        pickle_main = _identify_module(file, main)
        if main is None:
            main = pickle_main
        if isinstance(main, str):
            if main.startswith('__runtime__.'):
                # Create runtime module to load the session into.
                main = ModuleType(main.partition('.')[-1])
            else:
                main = _import_module(main)
        if not isinstance(main, ModuleType):
            raise TypeError("%r is not a module" % main)
        unpickler._main = main

        # Check against the pickle's main.
        is_main_imported = _is_imported_module(main)
        if pickle_main is not None:
            is_runtime_mod = pickle_main.startswith('__runtime__.')
            if is_runtime_mod:
                pickle_main = pickle_main.partition('.')[-1]
            error_msg = "can't update{} module{} %r with the saved state of{} module{} %r"
            if main.__name__ != pickle_main:
                raise ValueError(error_msg.format("", "", "", "") % (main.__name__, pickle_main))
            if is_runtime_mod and is_main_imported:
                raise ValueError(
                    error_msg.format(" imported", "", "", "-type object")
                    % (main.__name__, main.__name__)
                )
            if not is_runtime_mod and not is_main_imported:
                raise ValueError(
                    error_msg.format("", "-type object", " imported", "")
                    % (main.__name__, main.__name__)
                )

        try:
            if not is_main_imported:
                # This is for find_class() to be able to locate it.
                runtime_main = '__runtime__.%s' % main.__name__
                sys.modules[runtime_main] = main
            loaded = unpickler.load()
        finally:
            if not is_main_imported:
                del sys.modules[runtime_main]

    assert loaded is main
    _restore_modules(unpickler, main)
    if main is _main_module or main is module:
        return None
    else:
        return main

# Backward compatibility.
def load_session(filename=str(TEMPDIR/'session.pkl'), main=None, **kwds):
    warnings.warn("load_session() has been renamed load_module().", PendingDeprecationWarning)
    load_module(filename, module=main, **kwds)
load_session.__doc__ = load_module.__doc__

def load_module_asdict(
    filename = str(TEMPDIR/'session.pkl'),
    update: bool = False,
    **kwds
) -> dict:
    """
    Load the contents of a saved module into a dictionary.

    ``load_module_asdict()`` is the near-equivalent of::

        lambda filename: vars(dill.load_module(filename)).copy()

    however, does not alter the original module. Also, the path of
    the loaded module is stored in the ``__session__`` attribute.

    Parameters:
        filename: a path-like object or a readable stream
        update: if `True`, initialize the dictionary with the current state
            of the module prior to loading the state stored at filename.
        **kwds: extra keyword arguments passed to :py:class:`Unpickler()`

    Raises:
        :py:exc:`UnpicklingError`: if unpickling fails

    Returns:
        A copy of the restored module's dictionary.

    Note:
        If ``update`` is True, the corresponding module may first be imported
        into the current namespace before the saved state is loaded from
        filename to the dictionary. Note that any module that is imported into
        the current namespace as a side-effect of using ``update`` will not be
        modified by loading the saved module in filename to a dictionary.

    Example:
        >>> import dill
        >>> alist = [1, 2, 3]
        >>> anum = 42
        >>> dill.dump_module()
        >>> anum = 0
        >>> new_var = 'spam'
        >>> main = dill.load_module_asdict()
        >>> main['__name__'], main['__session__']
        ('__main__', '/tmp/session.pkl')
        >>> main is globals() # loaded objects don't reference globals
        False
        >>> main['alist'] == alist
        True
        >>> main['alist'] is alist # was saved by value
        False
        >>> main['anum'] == anum # changed after the session was saved
        False
        >>> new_var in main # would be True if the option 'update' was set
        False
    """
    if 'module' in kwds:
        raise TypeError("'module' is an invalid keyword argument for load_module_asdict()")
    with _open(filename, 'rb', peekable=True) as file:
        main_name = _identify_module(file)
        old_main = sys.modules.get(main_name)
        main = ModuleType(main_name)
        if update:
            if old_main is None:
                old_main = _import_module(main_name)
            main.__dict__.update(old_main.__dict__)
        else:
            main.__builtins__ = __builtin__
        try:
            sys.modules[main_name] = main
            load_module(file, **kwds)
        finally:
            if old_main is None:
                del sys.modules[main_name]
            else:
                sys.modules[main_name] = old_main
    main.__session__ = str(filename)
    return main.__dict__


# Internal exports for backward compatibility with dill v0.3.5.1
# Can't be placed in dill._dill because of circular import problems.
for name in (
    '_lookup_module', '_module_map', '_restore_modules', '_stash_modules',
    'dump_session', 'load_session' # backward compatibility functions
):
    setattr(_dill, name, globals()[name])
del name
