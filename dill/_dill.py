# -*- coding: utf-8 -*-
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2015 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
dill: a utility for serialization of python objects

Based on code written by Oren Tirosh and Armin Ronacher.
Extended to a (near) full set of the builtin types (in types module),
and coded to the pickle interface, by <mmckerns@caltech.edu>.
Initial port to python3 by Jonathan Dobson, continued by mmckerns.
Test against "all" python types (Std. Lib. CH 1-15 @ 2.7) by mmckerns.
Test against CH16+ Std. Lib. ... TBD.
"""
__all__ = [
    'dump', 'dumps', 'load', 'loads', 'dump_module', 'load_module',
    'load_module_asdict', 'dump_session', 'load_session', 'Pickler', 'Unpickler',
    'register', 'copy', 'pickle', 'pickles', 'check', 'HIGHEST_PROTOCOL',
    'DEFAULT_PROTOCOL', 'PicklingError', 'UnpicklingError', 'HANDLE_FMODE',
    'CONTENTS_FMODE', 'FILE_FMODE', 'PickleError', 'PickleWarning',
    'PicklingWarning', 'UnpicklingWarning'
]

__module__ = 'dill'

import warnings
from .logger import adapter as logger
from .logger import trace as _trace

from typing import Optional, Union

import os
import sys
diff = None
_use_diff = False
OLD38 = (sys.hexversion < 0x3080000)
OLD39 = (sys.hexversion < 0x3090000)
OLD310 = (sys.hexversion < 0x30a0000)
#XXX: get types from .objtypes ?
import builtins as __builtin__
from pickle import _Pickler as StockPickler, Unpickler as StockUnpickler
from _thread import LockType
from _thread import RLock as RLockType
#from io import IOBase
from types import CodeType, FunctionType, MethodType, GeneratorType, \
    TracebackType, FrameType, ModuleType, BuiltinMethodType
BufferType = memoryview #XXX: unregistered
ClassType = type # no 'old-style' classes
EllipsisType = type(Ellipsis)
#FileType = IOBase
NotImplementedType = type(NotImplemented)
SliceType = slice
TypeType = type # 'new-style' classes #XXX: unregistered
XRangeType = range
from types import MappingProxyType as DictProxyType
from pickle import DEFAULT_PROTOCOL, HIGHEST_PROTOCOL, PickleError, PicklingError, UnpicklingError
import __main__ as _main_module
import marshal
import gc
# import zlib
from weakref import ReferenceType, ProxyType, CallableProxyType
from collections import OrderedDict
from functools import partial
from operator import itemgetter, attrgetter
GENERATOR_FAIL = False
import importlib.machinery
EXTENSION_SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)
try:
    import ctypes
    HAS_CTYPES = True
    # if using `pypy`, pythonapi is not found
    IS_PYPY = not hasattr(ctypes, 'pythonapi')
except ImportError:
    HAS_CTYPES = False
    IS_PYPY = False
NumpyUfuncType = None
NumpyDType = None
NumpyArrayType = None
try:
    if not importlib.machinery.PathFinder().find_spec('numpy'):
        raise ImportError("No module named 'numpy'")
    NumpyUfuncType = True
    NumpyDType = True
    NumpyArrayType = True
except ImportError:
    pass
def __hook__():
    global NumpyArrayType, NumpyDType, NumpyUfuncType
    from numpy import ufunc as NumpyUfuncType
    from numpy import ndarray as NumpyArrayType
    from numpy import dtype as NumpyDType
    return True
if NumpyArrayType: # then has numpy
    def ndarraysubclassinstance(obj):
        if type(obj) in (TypeType, ClassType):
            return False # all classes return False
        try: # check if is ndarray, and elif is subclass of ndarray
            cls = getattr(obj, '__class__', None)
            if cls is None: return False
            elif cls is TypeType: return False
            elif 'numpy.ndarray' not in str(getattr(cls, 'mro', int.mro)()):
                return False
        except ReferenceError: return False # handle 'R3' weakref in 3.x
        except TypeError: return False
        # anything below here is a numpy array (or subclass) instance
        __hook__() # import numpy (so the following works!!!)
        # verify that __reduce__ has not been overridden
        NumpyInstance = NumpyArrayType((0,),'int8')
        if id(obj.__reduce_ex__) == id(NumpyInstance.__reduce_ex__) and \
           id(obj.__reduce__) == id(NumpyInstance.__reduce__): return True
        return False
    def numpyufunc(obj):
        if type(obj) in (TypeType, ClassType):
            return False # all classes return False
        try: # check if is ufunc
            cls = getattr(obj, '__class__', None)
            if cls is None: return False
            elif cls is TypeType: return False
            if 'numpy.ufunc' not in str(getattr(cls, 'mro', int.mro)()):
                return False
        except ReferenceError: return False # handle 'R3' weakref in 3.x
        except TypeError: return False
        # anything below here is a numpy ufunc
        return True
    def numpydtype(obj):
        if type(obj) in (TypeType, ClassType):
            return False # all classes return False
        try: # check if is dtype
            cls = getattr(obj, '__class__', None)
            if cls is None: return False
            elif cls is TypeType: return False
            if 'numpy.dtype' not in str(getattr(obj, 'mro', int.mro)()):
                return False
        except ReferenceError: return False # handle 'R3' weakref in 3.x
        except TypeError: return False
        # anything below here is a numpy dtype
        __hook__() # import numpy (so the following works!!!)
        return type(obj) is type(NumpyDType) # handles subclasses
else:
    def ndarraysubclassinstance(obj): return False
    def numpyufunc(obj): return False
    def numpydtype(obj): return False

from types import GetSetDescriptorType, ClassMethodDescriptorType, \
     WrapperDescriptorType,  MethodDescriptorType, MemberDescriptorType, \
     MethodWrapperType #XXX: unused

# make sure to add these 'hand-built' types to _typemap
CellType = type((lambda x: lambda y: x)(0).__closure__[0])
PartialType = type(partial(int, base=2))
SuperType = type(super(Exception, TypeError()))
ItemGetterType = type(itemgetter(0))
AttrGetterType = type(attrgetter('__repr__'))

try:
    from functools import _lru_cache_wrapper as LRUCacheType
except ImportError:
    LRUCacheType = None

if not isinstance(LRUCacheType, type):
    LRUCacheType = None

def get_file_type(*args, **kwargs):
    open = kwargs.pop("open", __builtin__.open)
    f = open(os.devnull, *args, **kwargs)
    t = type(f)
    f.close()
    return t

FileType = get_file_type('rb', buffering=0)
TextWrapperType = get_file_type('r', buffering=-1)
BufferedRandomType = get_file_type('r+b', buffering=-1)
BufferedReaderType = get_file_type('rb', buffering=-1)
BufferedWriterType = get_file_type('wb', buffering=-1)
try:
    from _pyio import open as _open
    PyTextWrapperType = get_file_type('r', buffering=-1, open=_open)
    PyBufferedRandomType = get_file_type('r+b', buffering=-1, open=_open)
    PyBufferedReaderType = get_file_type('rb', buffering=-1, open=_open)
    PyBufferedWriterType = get_file_type('wb', buffering=-1, open=_open)
except ImportError:
    PyTextWrapperType = PyBufferedRandomType = PyBufferedReaderType = PyBufferedWriterType = None
from io import BytesIO as StringIO
InputType = OutputType = None
from socket import socket as SocketType
#FIXME: additionally calls ForkingPickler.register several times
from multiprocessing.reduction import _reduce_socket as reduce_socket
try:
    __IPYTHON__ is True # is ipython
    ExitType = None     # IPython.core.autocall.ExitAutocall
    singletontypes = ['exit', 'quit', 'get_ipython']
except NameError:
    try: ExitType = type(exit) # apparently 'exit' can be removed
    except NameError: ExitType = None
    singletontypes = []

import inspect

### Shims for different versions of Python and dill
class Sentinel(object):
    """
    Create a unique sentinel object that is pickled as a constant.
    """
    def __init__(self, name, module_name=None):
        self.name = name
        if module_name is None:
            # Use the calling frame's module
            self.__module__ = inspect.currentframe().f_back.f_globals['__name__']
        else:
            self.__module__ = module_name # pragma: no cover
    def __repr__(self):
        return self.__module__ + '.' + self.name # pragma: no cover
    def __copy__(self):
        return self # pragma: no cover
    def __deepcopy__(self, memo):
        return self # pragma: no cover
    def __reduce__(self):
        return self.name
    def __reduce_ex__(self, protocol):
        return self.name

from . import _shims
from ._shims import Reduce, Getattr

### File modes
#: Pickles the file handle, preserving mode. The position of the unpickled
#: object is as for a new file handle.
HANDLE_FMODE = 0
#: Pickles the file contents, creating a new file if on load the file does
#: not exist. The position = min(pickled position, EOF) and mode is chosen
#: as such that "best" preserves behavior of the original file.
CONTENTS_FMODE = 1
#: Pickles the entire file (handle and contents), preserving mode and position.
FILE_FMODE = 2

### Shorthands (modified from python2.5/lib/pickle.py)
def copy(obj, *args, **kwds):
    """
    Use pickling to 'copy' an object (i.e. `loads(dumps(obj))`).

    See :func:`dumps` and :func:`loads` for keyword arguments.
    """
    ignore = kwds.pop('ignore', Unpickler.settings['ignore'])
    return loads(dumps(obj, *args, **kwds), ignore=ignore)

def dump(obj, file, protocol=None, byref=None, fmode=None, recurse=None, **kwds):#, strictio=None):
    """
    Pickle an object to a file.

    See :func:`dumps` for keyword arguments.
    """
    from .settings import settings
    protocol = settings['protocol'] if protocol is None else int(protocol)
    _kwds = kwds.copy()
    _kwds.update(dict(byref=byref, fmode=fmode, recurse=recurse))
    Pickler(file, protocol, **_kwds).dump(obj)
    return

def dumps(obj, protocol=None, byref=None, fmode=None, recurse=None, **kwds):#, strictio=None):
    """
    Pickle an object to a string.

    *protocol* is the pickler protocol, as defined for Python *pickle*.

    If *byref=True*, then dill behaves a lot more like pickle as certain
    objects (like modules) are pickled by reference as opposed to attempting
    to pickle the object itself.

    If *recurse=True*, then objects referred to in the global dictionary
    are recursively traced and pickled, instead of the default behavior
    of attempting to store the entire global dictionary. This is needed for
    functions defined via *exec()*.

    *fmode* (:const:`HANDLE_FMODE`, :const:`CONTENTS_FMODE`,
    or :const:`FILE_FMODE`) indicates how file handles will be pickled.
    For example, when pickling a data file handle for transfer to a remote
    compute service, *FILE_FMODE* will include the file contents in the
    pickle and cursor position so that a remote method can operate
    transparently on an object with an open file handle.

    Default values for keyword arguments can be set in :mod:`dill.settings`.
    """
    file = StringIO()
    dump(obj, file, protocol, byref, fmode, recurse, **kwds)#, strictio)
    return file.getvalue()

def load(file, ignore=None, **kwds):
    """
    Unpickle an object from a file.

    See :func:`loads` for keyword arguments.
    """
    return Unpickler(file, ignore=ignore, **kwds).load()

def loads(str, ignore=None, **kwds):
    """
    Unpickle an object from a string.

    If *ignore=False* then objects whose class is defined in the module
    *__main__* are updated to reference the existing class in *__main__*,
    otherwise they are left to refer to the reconstructed type, which may
    be different.

    Default values for keyword arguments can be set in :mod:`dill.settings`.
    """
    file = StringIO(str)
    return load(file, ignore, **kwds)

# def dumpzs(obj, protocol=None):
#     """pickle an object to a compressed string"""
#     return zlib.compress(dumps(obj, protocol))

# def loadzs(str):
#     """unpickle an object from a compressed string"""
#     return loads(zlib.decompress(str))

### End: Shorthands ###

### Pickle the Interpreter Session
import pathlib
import tempfile

SESSION_IMPORTED_AS_TYPES = (ModuleType, ClassType, TypeType, Exception,
                             FunctionType, MethodType, BuiltinMethodType)
TEMPDIR = pathlib.PurePath(tempfile.gettempdir())

def _module_map():
    """get map of imported modules"""
    from collections import defaultdict, namedtuple
    modmap = namedtuple('Modmap', ['by_name', 'by_id', 'top_level'])
    modmap = modmap(defaultdict(list), defaultdict(list), {})
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

#NOTE: 06/03/15 renamed main_module to main
def dump_module(
    filename = str(TEMPDIR/'session.pkl'),
    main: Optional[Union[ModuleType, str]] = None,
    refimported: bool = False,
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
    if main is None: main = _main_module
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
        pickler._main_modified = main is not pickler._original_main
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
    if not (module is _main_module or module is main_arg):
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
            main.__builtins__ = __builtin__
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

### End: Pickle the Interpreter

class MetaCatchingDict(dict):
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __missing__(self, key):
        if issubclass(key, type):
            return save_type
        else:
            raise KeyError()

class PickleWarning(Warning, PickleError):
    pass

class PicklingWarning(PickleWarning, PicklingError):
    pass

class UnpicklingWarning(PickleWarning, UnpicklingError):
    pass

### Extend the Picklers
class Pickler(StockPickler):
    """python's Pickler extended to interpreter sessions"""
    dispatch = MetaCatchingDict(StockPickler.dispatch.copy())
    _session = False
    from .settings import settings

    def __init__(self, file, *args, **kwds):
        settings = Pickler.settings
        _byref = kwds.pop('byref', None)
       #_strictio = kwds.pop('strictio', None)
        _fmode = kwds.pop('fmode', None)
        _recurse = kwds.pop('recurse', None)
        StockPickler.__init__(self, file, *args, **kwds)
        self._main = _main_module
        self._diff_cache = {}
        self._byref = settings['byref'] if _byref is None else _byref
        self._strictio = False #_strictio
        self._fmode = settings['fmode'] if _fmode is None else _fmode
        self._recurse = settings['recurse'] if _recurse is None else _recurse
        self._postproc = OrderedDict()
        self._file = file

    def dump(self, obj): #NOTE: if settings change, need to update attributes
        # register if the object is a numpy ufunc
        # thanks to Paul Kienzle for pointing out ufuncs didn't pickle
        if NumpyUfuncType and numpyufunc(obj):
            @register(type(obj))
            def save_numpy_ufunc(pickler, obj):
                logger.trace(pickler, "Nu: %s", obj)
                name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
                StockPickler.save_global(pickler, obj, name=name)
                logger.trace(pickler, "# Nu")
                return
            # NOTE: the above 'save' performs like:
            #   import copy_reg
            #   def udump(f): return f.__name__
            #   def uload(name): return getattr(numpy, name)
            #   copy_reg.pickle(NumpyUfuncType, udump, uload)
        # register if the object is a numpy dtype
        if NumpyDType and numpydtype(obj):
            @register(type(obj))
            def save_numpy_dtype(pickler, obj):
                logger.trace(pickler, "Dt: %s", obj)
                pickler.save_reduce(_create_dtypemeta, (obj.type,), obj=obj)
                logger.trace(pickler, "# Dt")
                return
            # NOTE: the above 'save' performs like:
            #   import copy_reg
            #   def uload(name): return type(NumpyDType(name))
            #   def udump(f): return uload, (f.type,)
            #   copy_reg.pickle(NumpyDTypeType, udump, uload)
        # register if the object is a subclassed numpy array instance
        if NumpyArrayType and ndarraysubclassinstance(obj):
            @register(type(obj))
            def save_numpy_array(pickler, obj):
                logger.trace(pickler, "Nu: (%s, %s)", obj.shape, obj.dtype)
                npdict = getattr(obj, '__dict__', None)
                f, args, state = obj.__reduce__()
                pickler.save_reduce(_create_array, (f,args,state,npdict), obj=obj)
                logger.trace(pickler, "# Nu")
                return
        # end hack
        if GENERATOR_FAIL and type(obj) == GeneratorType:
            msg = "Can't pickle %s: attribute lookup builtins.generator failed" % GeneratorType
            raise PicklingError(msg)
        logger.trace_setup(self)
        StockPickler.dump(self, obj)

    dump.__doc__ = StockPickler.dump.__doc__

class Unpickler(StockUnpickler):
    """python's Unpickler extended to interpreter sessions and more types"""
    from .settings import settings
    _session = False

    def find_class(self, module, name):
        if (module, name) == ('__builtin__', '__main__'):
            return self._main.__dict__ #XXX: above set w/save_module_dict
        elif (module, name) == ('__builtin__', 'NoneType'):
            return type(None) #XXX: special case: NoneType missing
        if module == 'dill.dill': module = 'dill._dill'
        return StockUnpickler.find_class(self, module, name)

    def __init__(self, *args, **kwds):
        settings = Pickler.settings
        _ignore = kwds.pop('ignore', None)
        StockUnpickler.__init__(self, *args, **kwds)
        self._main = _main_module
        self._ignore = settings['ignore'] if _ignore is None else _ignore

    def load(self): #NOTE: if settings change, need to update attributes
        obj = StockUnpickler.load(self)
        if type(obj).__module__ == getattr(_main_module, '__name__', '__main__'):
            if not self._ignore:
                # point obj class to main
                try: obj.__class__ = getattr(self._main, type(obj).__name__)
                except (AttributeError,TypeError): pass # defined in a file
       #_main_module.__dict__.update(obj.__dict__) #XXX: should update globals ?
        return obj
    load.__doc__ = StockUnpickler.load.__doc__
    pass

'''
def dispatch_table():
    """get the dispatch table of registered types"""
    return Pickler.dispatch
'''

pickle_dispatch_copy = StockPickler.dispatch.copy()

def pickle(t, func):
    """expose dispatch table for user-created extensions"""
    Pickler.dispatch[t] = func
    return

def register(t):
    """register type to Pickler's dispatch table """
    def proxy(func):
        Pickler.dispatch[t] = func
        return func
    return proxy

def _revert_extension():
    """drop dill-registered types from pickle's dispatch table"""
    for type, func in list(StockPickler.dispatch.items()):
        if func.__module__ == __name__:
            del StockPickler.dispatch[type]
            if type in pickle_dispatch_copy:
                StockPickler.dispatch[type] = pickle_dispatch_copy[type]

def use_diff(on=True):
    """
    Reduces size of pickles by only including object which have changed.

    Decreases pickle size but increases CPU time needed.
    Also helps avoid some unpicklable objects.
    MUST be called at start of script, otherwise changes will not be recorded.
    """
    global _use_diff, diff
    _use_diff = on
    if _use_diff and diff is None:
        try:
            from . import diff as d
        except ImportError:
            import diff as d
        diff = d

def _create_typemap():
    import types
    d = dict(list(__builtin__.__dict__.items()) + \
             list(types.__dict__.items())).items()
    for key, value in d:
        if getattr(value, '__module__', None) == 'builtins' \
                and type(value) is type:
            yield key, value
    return
_reverse_typemap = dict(_create_typemap())
_reverse_typemap.update({
    'CellType': CellType,
    'PartialType': PartialType,
    'SuperType': SuperType,
    'ItemGetterType': ItemGetterType,
    'AttrGetterType': AttrGetterType,
})

# "Incidental" implementation specific types. Unpickling these types in another
# implementation of Python (PyPy -> CPython) is not guaranteed to work

# This dictionary should contain all types that appear in Python implementations
# but are not defined in https://docs.python.org/3/library/types.html#standard-interpreter-types
x=OrderedDict()
_incedental_reverse_typemap = {
    'FileType': FileType,
    'BufferedRandomType': BufferedRandomType,
    'BufferedReaderType': BufferedReaderType,
    'BufferedWriterType': BufferedWriterType,
    'TextWrapperType': TextWrapperType,
    'PyBufferedRandomType': PyBufferedRandomType,
    'PyBufferedReaderType': PyBufferedReaderType,
    'PyBufferedWriterType': PyBufferedWriterType,
    'PyTextWrapperType': PyTextWrapperType,
}

_incedental_reverse_typemap.update({
    "DictKeysType": type({}.keys()),
    "DictValuesType": type({}.values()),
    "DictItemsType": type({}.items()),

    "OdictKeysType": type(x.keys()),
    "OdictValuesType": type(x.values()),
    "OdictItemsType": type(x.items()),
})

if ExitType:
    _incedental_reverse_typemap['ExitType'] = ExitType
if InputType:
    _incedental_reverse_typemap['InputType'] = InputType
    _incedental_reverse_typemap['OutputType'] = OutputType

'''
try:
    import symtable
    _incedental_reverse_typemap["SymtableEntryType"] = type(symtable.symtable("", "string", "exec")._table)
except: #FIXME: fails to pickle
    pass
'''

if sys.hexversion >= 0x30a00a0:
    _incedental_reverse_typemap['LineIteratorType'] = type(compile('3', '', 'eval').co_lines())

if sys.hexversion >= 0x30b00b0:
    from types import GenericAlias
    _incedental_reverse_typemap["GenericAliasIteratorType"] = type(iter(GenericAlias(list, (int,))))
    _incedental_reverse_typemap['PositionsIteratorType'] = type(compile('3', '', 'eval').co_positions())

try:
    import winreg
    _incedental_reverse_typemap["HKEYType"] = winreg.HKEYType
except ImportError:
    pass

_reverse_typemap.update(_incedental_reverse_typemap)
_incedental_types = set(_incedental_reverse_typemap.values())

del x

_typemap = dict((v, k) for k, v in _reverse_typemap.items())

def _unmarshal(string):
    return marshal.loads(string)

def _load_type(name):
    return _reverse_typemap[name]

def _create_type(typeobj, *args):
    return typeobj(*args)

def _create_function(fcode, fglobals, fname=None, fdefaults=None,
                     fclosure=None, fdict=None, fkwdefaults=None):
    # same as FunctionType, but enable passing __dict__ to new function,
    # __dict__ is the storehouse for attributes added after function creation
    func = FunctionType(fcode, fglobals or dict(), fname, fdefaults, fclosure)
    if fdict is not None:
        func.__dict__.update(fdict) #XXX: better copy? option to copy?
    if fkwdefaults is not None:
        func.__kwdefaults__ = fkwdefaults
    # 'recurse' only stores referenced modules/objects in fglobals,
    # thus we need to make sure that we have __builtins__ as well
    if "__builtins__" not in func.__globals__:
        func.__globals__["__builtins__"] = globals()["__builtins__"]
    # assert id(fglobals) == id(func.__globals__)
    return func

class match:
    """
    Make avaialable a limited structural pattern matching-like syntax for Python < 3.10

    Patterns can be only tuples (without types) currently.
    Inspired by the package pattern-matching-PEP634.

    Usage:
    >>> with match(args) as m:
    >>>     if   m.case(('x', 'y')):
    >>>         # use m.x and m.y
    >>>     elif m.case(('x', 'y', 'z')):
    >>>         # use m.x, m.y and m.z

    Equivalent native code for Python >= 3.10:
    >>> match args:
    >>>     case (x, y):
    >>>         # use x and y
    >>>     case (x, y, z):
    >>>         # use x, y and z
    """
    def __init__(self, value):
        self.value = value
        self._fields = None
    def __enter__(self):
        return self
    def __exit__(self, *exc_info):
        return False
    def case(self, args): # *args, **kwargs):
        """just handles tuple patterns"""
        if len(self.value) != len(args): # + len(kwargs):
            return False
        #if not all(isinstance(arg, pat) for arg, pat in zip(self.value[len(args):], kwargs.values())):
        #    return False
        self.args = args # (*args, *kwargs)
        return True
    @property
    def fields(self):
        # Only bind names to values if necessary.
        if self._fields is None:
            self._fields = dict(zip(self.args, self.value))
        return self._fields
    def __getattr__(self, item):
        return self.fields[item]

ALL_CODE_PARAMS = [
    # Version     New attribute         CodeType parameters
    ((3,11,'a'), 'co_endlinetable',    'argcount posonlyargcount kwonlyargcount nlocals stacksize flags code consts names varnames filename name qualname firstlineno linetable endlinetable columntable exceptiontable freevars cellvars'),
    ((3,11),     'co_exceptiontable',  'argcount posonlyargcount kwonlyargcount nlocals stacksize flags code consts names varnames filename name qualname firstlineno linetable                          exceptiontable freevars cellvars'),
    ((3,10),     'co_linetable',       'argcount posonlyargcount kwonlyargcount nlocals stacksize flags code consts names varnames filename name          firstlineno linetable                                         freevars cellvars'),
    ((3,8),      'co_posonlyargcount', 'argcount posonlyargcount kwonlyargcount nlocals stacksize flags code consts names varnames filename name          firstlineno lnotab                                            freevars cellvars'),
    ((3,7),      'co_kwonlyargcount',  'argcount                 kwonlyargcount nlocals stacksize flags code consts names varnames filename name          firstlineno lnotab                                            freevars cellvars'),
    ]
for version, new_attr, params in ALL_CODE_PARAMS:
    if hasattr(CodeType, new_attr):
        CODE_VERSION = version
        CODE_PARAMS = params.split()
        break
ENCODE_PARAMS = set(CODE_PARAMS).intersection(
        ['code', 'lnotab', 'linetable', 'endlinetable', 'columntable', 'exceptiontable'])

def _create_code(*args):
    if not isinstance(args[0], int): # co_lnotab stored from >= 3.10
        LNOTAB, *args = args
    else: # from < 3.10 (or pre-LNOTAB storage)
        LNOTAB = b''

    with match(args) as m:
        # Python 3.11/3.12a (18 members)
        if m.case((
            'argcount', 'posonlyargcount', 'kwonlyargcount', 'nlocals', 'stacksize', 'flags',     # args[0:6]
            'code', 'consts', 'names', 'varnames', 'filename', 'name', 'qualname', 'firstlineno', # args[6:14]
            'linetable', 'exceptiontable', 'freevars', 'cellvars'                                 # args[14:]
        )):
            if CODE_VERSION == (3,11):
                return CodeType(
                    *args[:6],
                    args[6].encode() if hasattr(args[6], 'encode') else args[6], # code
                    *args[7:14],
                    args[14].encode() if hasattr(args[14], 'encode') else args[14], # linetable
                    args[15].encode() if hasattr(args[15], 'encode') else args[15], # exceptiontable
                    args[16],
                    args[17],
                )
            fields = m.fields
        # Python 3.10 or 3.8/3.9 (16 members)
        elif m.case((
            'argcount', 'posonlyargcount', 'kwonlyargcount', 'nlocals', 'stacksize', 'flags', # args[0:6]
            'code', 'consts', 'names', 'varnames', 'filename', 'name', 'firstlineno',         # args[6:13]
            'LNOTAB_OR_LINETABLE', 'freevars', 'cellvars'                                     # args[13:]
        )):
            if CODE_VERSION == (3,10) or CODE_VERSION == (3,8):
                return CodeType(
                    *args[:6],
                    args[6].encode() if hasattr(args[6], 'encode') else args[6], # code
                    *args[7:13],
                    args[13].encode() if hasattr(args[13], 'encode') else args[13], # lnotab/linetable
                    args[14],
                    args[15],
                )
            fields = m.fields
            if CODE_VERSION >= (3,10):
                fields['linetable'] = m.LNOTAB_OR_LINETABLE
            else:
                fields['lnotab'] = LNOTAB if LNOTAB else m.LNOTAB_OR_LINETABLE
        # Python 3.7 (15 args)
        elif m.case((
            'argcount', 'kwonlyargcount', 'nlocals', 'stacksize', 'flags',            # args[0:5]
            'code', 'consts', 'names', 'varnames', 'filename', 'name', 'firstlineno', # args[5:12]
            'lnotab', 'freevars', 'cellvars'                                          # args[12:]
        )):
            if CODE_VERSION == (3,7):
                return CodeType(
                    *args[:5],
                    args[5].encode() if hasattr(args[5], 'encode') else args[5], # code
                    *args[6:12],
                    args[12].encode() if hasattr(args[12], 'encode') else args[12], # lnotab
                    args[13],
                    args[14],
                )
            fields = m.fields
        # Python 3.11a (20 members)
        elif m.case((
            'argcount', 'posonlyargcount', 'kwonlyargcount', 'nlocals', 'stacksize', 'flags',     # args[0:6]
            'code', 'consts', 'names', 'varnames', 'filename', 'name', 'qualname', 'firstlineno', # args[6:14]
            'linetable', 'endlinetable', 'columntable', 'exceptiontable', 'freevars', 'cellvars'  # args[14:]
        )):
            if CODE_VERSION == (3,11,'a'):
                return CodeType(
                    *args[:6],
                    args[6].encode() if hasattr(args[6], 'encode') else args[6], # code
                    *args[7:14],
                    *(a.encode() if hasattr(a, 'encode') else a for a in args[14:18]), # linetable-exceptiontable
                    args[18],
                    args[19],
                )
            fields = m.fields
        else:
            raise UnpicklingError("pattern match for code object failed")

    # The args format doesn't match this version.
    fields.setdefault('posonlyargcount', 0)         # from python <= 3.7
    fields.setdefault('lnotab', LNOTAB)             # from python >= 3.10
    fields.setdefault('linetable', b'')             # from python <= 3.9
    fields.setdefault('qualname', fields['name'])   # from python <= 3.10
    fields.setdefault('exceptiontable', b'')        # from python <= 3.10
    fields.setdefault('endlinetable', None)         # from python != 3.11a
    fields.setdefault('columntable', None)          # from python != 3.11a

    args = (fields[k].encode() if k in ENCODE_PARAMS and hasattr(fields[k], 'encode') else fields[k]
            for k in CODE_PARAMS)
    return CodeType(*args)

def _create_ftype(ftypeobj, func, args, kwds):
    if kwds is None:
        kwds = {}
    if args is None:
        args = ()
    return ftypeobj(func, *args, **kwds)

def _create_lock(locked, *args): #XXX: ignores 'blocking'
    from threading import Lock
    lock = Lock()
    if locked:
        if not lock.acquire(False):
            raise UnpicklingError("Cannot acquire lock")
    return lock

def _create_rlock(count, owner, *args): #XXX: ignores 'blocking'
    lock = RLockType()
    if owner is not None:
        lock._acquire_restore((count, owner))
    if owner and not lock._is_owned():
        raise UnpicklingError("Cannot acquire lock")
    return lock

# thanks to matsjoyce for adding all the different file modes
def _create_filehandle(name, mode, position, closed, open, strictio, fmode, fdata): # buffering=0
    # only pickles the handle, not the file contents... good? or StringIO(data)?
    # (for file contents see: http://effbot.org/librarybook/copy-reg.htm)
    # NOTE: handle special cases first (are there more special cases?)
    names = {'<stdin>':sys.__stdin__, '<stdout>':sys.__stdout__,
             '<stderr>':sys.__stderr__} #XXX: better fileno=(0,1,2) ?
    if name in list(names.keys()):
        f = names[name] #XXX: safer "f=sys.stdin"
    elif name == '<tmpfile>':
        f = os.tmpfile()
    elif name == '<fdopen>':
        import tempfile
        f = tempfile.TemporaryFile(mode)
    else:
        try:
            exists = os.path.exists(name)
        except Exception:
            exists = False
        if not exists:
            if strictio:
                raise FileNotFoundError("[Errno 2] No such file or directory: '%s'" % name)
            elif "r" in mode and fmode != FILE_FMODE:
                name = '<fdopen>' # or os.devnull?
            current_size = 0 # or maintain position?
        else:
            current_size = os.path.getsize(name)

        if position > current_size:
            if strictio:
                raise ValueError("invalid buffer size")
            elif fmode == CONTENTS_FMODE:
                position = current_size
        # try to open the file by name
        # NOTE: has different fileno
        try:
            #FIXME: missing: *buffering*, encoding, softspace
            if fmode == FILE_FMODE:
                f = open(name, mode if "w" in mode else "w")
                f.write(fdata)
                if "w" not in mode:
                    f.close()
                    f = open(name, mode)
            elif name == '<fdopen>': # file did not exist
                import tempfile
                f = tempfile.TemporaryFile(mode)
            # treat x mode as w mode
            elif fmode == CONTENTS_FMODE \
               and ("w" in mode or "x" in mode):
                # stop truncation when opening
                flags = os.O_CREAT
                if "+" in mode:
                    flags |= os.O_RDWR
                else:
                    flags |= os.O_WRONLY
                f = os.fdopen(os.open(name, flags), mode)
                # set name to the correct value
                r = getattr(f, "buffer", f)
                r = getattr(r, "raw", r)
                r.name = name
                assert f.name == name
            else:
                f = open(name, mode)
        except (IOError, FileNotFoundError):
            err = sys.exc_info()[1]
            raise UnpicklingError(err)
    if closed:
        f.close()
    elif position >= 0 and fmode != HANDLE_FMODE:
        f.seek(position)
    return f

def _create_stringi(value, position, closed):
    f = StringIO(value)
    if closed: f.close()
    else: f.seek(position)
    return f

def _create_stringo(value, position, closed):
    f = StringIO()
    if closed: f.close()
    else:
       f.write(value)
       f.seek(position)
    return f

class _itemgetter_helper(object):
    def __init__(self):
        self.items = []
    def __getitem__(self, item):
        self.items.append(item)
        return

class _attrgetter_helper(object):
    def __init__(self, attrs, index=None):
        self.attrs = attrs
        self.index = index
    def __getattribute__(self, attr):
        attrs = object.__getattribute__(self, "attrs")
        index = object.__getattribute__(self, "index")
        if index is None:
            index = len(attrs)
            attrs.append(attr)
        else:
            attrs[index] = ".".join([attrs[index], attr])
        return type(self)(attrs, index)

class _dictproxy_helper(dict):
   def __ror__(self, a):
        return a

_dictproxy_helper_instance = _dictproxy_helper()

__d = {}
try:
    # In CPython 3.9 and later, this trick can be used to exploit the
    # implementation of the __or__ function of MappingProxyType to get the true
    # mapping referenced by the proxy. It may work for other implementations,
    # but is not guaranteed.
    MAPPING_PROXY_TRICK = __d is (DictProxyType(__d) | _dictproxy_helper_instance)
except Exception:
    MAPPING_PROXY_TRICK = False
del __d

# _CELL_REF and _CELL_EMPTY are used to stay compatible with versions of dill
# whose _create_cell functions do not have a default value.
# _CELL_REF can be safely removed entirely (replaced by empty tuples for calls
# to _create_cell) once breaking changes are allowed.
_CELL_REF = None
_CELL_EMPTY = Sentinel('_CELL_EMPTY')

def _create_cell(contents=None):
    if contents is not _CELL_EMPTY:
        value = contents
    return (lambda: value).__closure__[0]

def _create_weakref(obj, *args):
    from weakref import ref
    if obj is None: # it's dead
        from collections import UserDict
        return ref(UserDict(), *args)
    return ref(obj, *args)

def _create_weakproxy(obj, callable=False, *args):
    from weakref import proxy
    if obj is None: # it's dead
        if callable: return proxy(lambda x:x, *args)
        from collections import UserDict
        return proxy(UserDict(), *args)
    return proxy(obj, *args)

def _eval_repr(repr_str):
    return eval(repr_str)

def _create_array(f, args, state, npdict=None):
   #array = numpy.core.multiarray._reconstruct(*args)
    array = f(*args)
    array.__setstate__(state)
    if npdict is not None: # we also have saved state in __dict__
        array.__dict__.update(npdict)
    return array

def _create_dtypemeta(scalar_type):
    if NumpyDType is True: __hook__() # a bit hacky I think
    if scalar_type is None:
        return NumpyDType
    return type(NumpyDType(scalar_type))

def _create_namedtuple(name, fieldnames, modulename, defaults=None):
    class_ = _import_module(modulename + '.' + name, safe=True)
    if class_ is not None:
        return class_
    import collections
    t = collections.namedtuple(name, fieldnames, defaults=defaults, module=modulename)
    return t

def _create_capsule(pointer, name, context, destructor):
    attr_found = False
    try:
        # based on https://github.com/python/cpython/blob/f4095e53ab708d95e019c909d5928502775ba68f/Objects/capsule.c#L209-L231
        uname = name.decode('utf8')
        for i in range(1, uname.count('.')+1):
            names = uname.rsplit('.', i)
            try:
                module = __import__(names[0])
            except ImportError:
                pass
            obj = module
            for attr in names[1:]:
                obj = getattr(obj, attr)
            capsule = obj
            attr_found = True
            break
    except Exception:
        pass

    if attr_found:
        if _PyCapsule_IsValid(capsule, name):
            return capsule
        raise UnpicklingError("%s object exists at %s but a PyCapsule object was expected." % (type(capsule), name))
    else:
        warnings.warn('Creating a new PyCapsule %s for a C data structure that may not be present in memory. Segmentation faults or other memory errors are possible.' % (name,), UnpicklingWarning)
        capsule = _PyCapsule_New(pointer, name, destructor)
        _PyCapsule_SetContext(capsule, context)
        return capsule

def _getattr(objclass, name, repr_str):
    # hack to grab the reference directly
    try: #XXX: works only for __builtin__ ?
        attr = repr_str.split("'")[3]
        return eval(attr+'.__dict__["'+name+'"]')
    except Exception:
        try:
            attr = objclass.__dict__
            if type(attr) is DictProxyType:
                attr = attr[name]
            else:
                attr = getattr(objclass,name)
        except (AttributeError, KeyError):
            attr = getattr(objclass,name)
        return attr

def _get_attr(self, name):
    # stop recursive pickling
    return getattr(self, name, None) or getattr(__builtin__, name)

def _dict_from_dictproxy(dictproxy):
    _dict = dictproxy.copy() # convert dictproxy to dict
    _dict.pop('__dict__', None)
    _dict.pop('__weakref__', None)
    _dict.pop('__prepare__', None)
    return _dict

def _import_module(import_name, safe=False):
    try:
        if import_name.startswith('__runtime__.'):
            return sys.modules[import_name]
        elif '.' in import_name:
            items = import_name.split('.')
            module = '.'.join(items[:-1])
            obj = items[-1]
        else:
            return __import__(import_name)
        return getattr(__import__(module, None, None, [obj]), obj)
    except (ImportError, AttributeError, KeyError):
        if safe:
            return None
        raise

# https://github.com/python/cpython/blob/a8912a0f8d9eba6d502c37d522221f9933e976db/Lib/pickle.py#L322-L333
def _getattribute(obj, name):
    for subpath in name.split('.'):
        if subpath == '<locals>':
            raise AttributeError("Can't get local attribute {!r} on {!r}"
                                 .format(name, obj))
        try:
            parent = obj
            obj = getattr(obj, subpath)
        except AttributeError:
            raise AttributeError("Can't get attribute {!r} on {!r}"
                                 .format(name, obj))
    return obj, parent

def _locate_function(obj, pickler=None):
    module_name = getattr(obj, '__module__', None)
    if module_name in ['__main__', None] or \
            pickler and is_dill(pickler, child=False) and pickler._session and module_name == pickler._main.__name__:
        return False
    if hasattr(obj, '__qualname__'):
        module = _import_module(module_name, safe=True)
        try:
            found, _ = _getattribute(module, obj.__qualname__)
            return found is obj
        except AttributeError:
            return False
    else:
        found = _import_module(module_name + '.' + obj.__name__, safe=True)
        return found is obj


def _setitems(dest, source):
    for k, v in source.items():
        dest[k] = v


def _save_with_postproc(pickler, reduction, is_pickler_dill=None, obj=Getattr.NO_DEFAULT, postproc_list=None):
    if obj is Getattr.NO_DEFAULT:
        obj = Reduce(reduction) # pragma: no cover

    if is_pickler_dill is None:
        is_pickler_dill = is_dill(pickler, child=True)
    if is_pickler_dill:
        # assert id(obj) not in pickler._postproc, str(obj) + ' already pushed on stack!'
        # if not hasattr(pickler, 'x'): pickler.x = 0
        # print(pickler.x*' ', 'push', obj, id(obj), pickler._recurse)
        # pickler.x += 1
        if postproc_list is None:
            postproc_list = []

        # Recursive object not supported. Default to a global instead.
        if id(obj) in pickler._postproc:
            name = '%s.%s ' % (obj.__module__, getattr(obj, '__qualname__', obj.__name__)) if hasattr(obj, '__module__') else ''
            warnings.warn('Cannot pickle %r: %shas recursive self-references that trigger a RecursionError.' % (obj, name), PicklingWarning)
            pickler.save_global(obj)
            return
        pickler._postproc[id(obj)] = postproc_list

    # TODO: Use state_setter in Python 3.8 to allow for faster cPickle implementations
    pickler.save_reduce(*reduction, obj=obj)

    if is_pickler_dill:
        # pickler.x -= 1
        # print(pickler.x*' ', 'pop', obj, id(obj))
        postproc = pickler._postproc.pop(id(obj))
        # assert postproc_list == postproc, 'Stack tampered!'
        for reduction in reversed(postproc):
            if reduction[0] is _setitems:
                # use the internal machinery of pickle.py to speedup when
                # updating a dictionary in postproc
                dest, source = reduction[1]
                if source:
                    pickler.write(pickler.get(pickler.memo[id(dest)][0]))
                    pickler._batch_setitems(iter(source.items()))
                else:
                    # Updating with an empty dictionary. Same as doing nothing.
                    continue
            else:
                pickler.save_reduce(*reduction)
            # pop None created by calling preprocessing step off stack
            pickler.write(bytes('0', 'UTF-8'))

#@register(CodeType)
#def save_code(pickler, obj):
#    logger.trace(pickler, "Co: %s", obj)
#    pickler.save_reduce(_unmarshal, (marshal.dumps(obj),), obj=obj)
#    logger.trace(pickler, "# Co")
#    return

# The following function is based on 'save_codeobject' from 'cloudpickle'
# Copyright (c) 2012, Regents of the University of California.
# Copyright (c) 2009 `PiCloud, Inc. <http://www.picloud.com>`_.
# License: https://github.com/cloudpipe/cloudpickle/blob/master/LICENSE
@register(CodeType)
def save_code(pickler, obj):
    logger.trace(pickler, "Co: %s", obj)
    if hasattr(obj, "co_endlinetable"): # python 3.11a (20 args)
        args = (
            obj.co_lnotab, # for < python 3.10 [not counted in args]
            obj.co_argcount, obj.co_posonlyargcount,
            obj.co_kwonlyargcount, obj.co_nlocals, obj.co_stacksize,
            obj.co_flags, obj.co_code, obj.co_consts, obj.co_names,
            obj.co_varnames, obj.co_filename, obj.co_name, obj.co_qualname,
            obj.co_firstlineno, obj.co_linetable, obj.co_endlinetable,
            obj.co_columntable, obj.co_exceptiontable, obj.co_freevars,
            obj.co_cellvars
    )
    elif hasattr(obj, "co_exceptiontable"): # python 3.11 (18 args)
        args = (
            obj.co_lnotab, # for < python 3.10 [not counted in args]
            obj.co_argcount, obj.co_posonlyargcount,
            obj.co_kwonlyargcount, obj.co_nlocals, obj.co_stacksize,
            obj.co_flags, obj.co_code, obj.co_consts, obj.co_names,
            obj.co_varnames, obj.co_filename, obj.co_name, obj.co_qualname,
            obj.co_firstlineno, obj.co_linetable, obj.co_exceptiontable,
            obj.co_freevars, obj.co_cellvars
    )
    elif hasattr(obj, "co_linetable"): # python 3.10 (16 args)
        args = (
            obj.co_lnotab, # for < python 3.10 [not counted in args]
            obj.co_argcount, obj.co_posonlyargcount,
            obj.co_kwonlyargcount, obj.co_nlocals, obj.co_stacksize,
            obj.co_flags, obj.co_code, obj.co_consts, obj.co_names,
            obj.co_varnames, obj.co_filename, obj.co_name,
            obj.co_firstlineno, obj.co_linetable, obj.co_freevars,
            obj.co_cellvars
    )
    elif hasattr(obj, "co_posonlyargcount"): # python 3.8 (16 args)
        args = (
            obj.co_argcount, obj.co_posonlyargcount,
            obj.co_kwonlyargcount, obj.co_nlocals, obj.co_stacksize,
            obj.co_flags, obj.co_code, obj.co_consts, obj.co_names,
            obj.co_varnames, obj.co_filename, obj.co_name,
            obj.co_firstlineno, obj.co_lnotab, obj.co_freevars,
            obj.co_cellvars
    )
    else: # python 3.7 (15 args)
        args = (
            obj.co_argcount, obj.co_kwonlyargcount, obj.co_nlocals,
            obj.co_stacksize, obj.co_flags, obj.co_code, obj.co_consts,
            obj.co_names, obj.co_varnames, obj.co_filename,
            obj.co_name, obj.co_firstlineno, obj.co_lnotab,
            obj.co_freevars, obj.co_cellvars
    )

    pickler.save_reduce(_create_code, args, obj=obj)
    logger.trace(pickler, "# Co")
    return

def _repr_dict(obj):
    """make a short string representation of a dictionary"""
    return "<%s object at %#012x>" % (type(obj).__name__, id(obj))

@register(dict)
def save_module_dict(pickler, obj):
    if is_dill(pickler, child=False) and obj == pickler._main.__dict__ and \
            not (pickler._session and pickler._first_pass):
        logger.trace(pickler, "D1: %s", _repr_dict(obj)) # obj
        pickler.write(bytes('c__builtin__\n__main__\n', 'UTF-8'))
        logger.trace(pickler, "# D1")
    elif (not is_dill(pickler, child=False)) and (obj == _main_module.__dict__):
        logger.trace(pickler, "D3: %s", _repr_dict(obj)) # obj
        pickler.write(bytes('c__main__\n__dict__\n', 'UTF-8'))  #XXX: works in general?
        logger.trace(pickler, "# D3")
    elif '__name__' in obj and obj != _main_module.__dict__ \
            and type(obj['__name__']) is str \
            and obj is getattr(_import_module(obj['__name__'],True), '__dict__', None):
        logger.trace(pickler, "D4: %s", _repr_dict(obj)) # obj
        pickler.write(bytes('c%s\n__dict__\n' % obj['__name__'], 'UTF-8'))
        logger.trace(pickler, "# D4")
    else:
        logger.trace(pickler, "D2: %s", _repr_dict(obj)) # obj
        if is_dill(pickler, child=False) and pickler._session:
            # we only care about session the first pass thru
            pickler._first_pass = False
        StockPickler.save_dict(pickler, obj)
        logger.trace(pickler, "# D2")
    return


if not OLD310 and MAPPING_PROXY_TRICK:
    def save_dict_view(dicttype):
        def save_dict_view_for_function(func):
            def _save_dict_view(pickler, obj):
                logger.trace(pickler, "Dkvi: <%s>", obj)
                mapping = obj.mapping | _dictproxy_helper_instance
                pickler.save_reduce(func, (mapping,), obj=obj)
                logger.trace(pickler, "# Dkvi")
            return _save_dict_view
        return [
            (funcname, save_dict_view_for_function(getattr(dicttype, funcname)))
            for funcname in ('keys', 'values', 'items')
        ]
else:
    # The following functions are based on 'cloudpickle'
    # https://github.com/cloudpipe/cloudpickle/blob/5d89947288a18029672596a4d719093cc6d5a412/cloudpickle/cloudpickle.py#L922-L940
    # Copyright (c) 2012, Regents of the University of California.
    # Copyright (c) 2009 `PiCloud, Inc. <http://www.picloud.com>`_.
    # License: https://github.com/cloudpipe/cloudpickle/blob/master/LICENSE
    def save_dict_view(dicttype):
        def save_dict_keys(pickler, obj):
            logger.trace(pickler, "Dk: <%s>", obj)
            dict_constructor = _shims.Reduce(dicttype.fromkeys, (list(obj),))
            pickler.save_reduce(dicttype.keys, (dict_constructor,), obj=obj)
            logger.trace(pickler, "# Dk")

        def save_dict_values(pickler, obj):
            logger.trace(pickler, "Dv: <%s>", obj)
            dict_constructor = _shims.Reduce(dicttype, (enumerate(obj),))
            pickler.save_reduce(dicttype.values, (dict_constructor,), obj=obj)
            logger.trace(pickler, "# Dv")

        def save_dict_items(pickler, obj):
            logger.trace(pickler, "Di: <%s>", obj)
            pickler.save_reduce(dicttype.items, (dicttype(obj),), obj=obj)
            logger.trace(pickler, "# Di")

        return (
            ('keys', save_dict_keys),
            ('values', save_dict_values),
            ('items', save_dict_items)
        )

for __dicttype in (
      dict,
      OrderedDict
):
    __obj = __dicttype()
    for __funcname, __savefunc in save_dict_view(__dicttype):
        __tview = type(getattr(__obj, __funcname)())
        if __tview not in Pickler.dispatch:
            Pickler.dispatch[__tview] = __savefunc
del __dicttype, __obj, __funcname, __tview, __savefunc


@register(ClassType)
def save_classobj(pickler, obj): #FIXME: enable pickler._byref
    if not _locate_function(obj, pickler):
        logger.trace(pickler, "C1: %s", obj)
        pickler.save_reduce(ClassType, (obj.__name__, obj.__bases__,
                                        obj.__dict__), obj=obj)
                                       #XXX: or obj.__dict__.copy()), obj=obj) ?
        logger.trace(pickler, "# C1")
    else:
        logger.trace(pickler, "C2: %s", obj)
        name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
        StockPickler.save_global(pickler, obj, name=name)
        logger.trace(pickler, "# C2")
    return

@register(LockType)
def save_lock(pickler, obj):
    logger.trace(pickler, "Lo: %s", obj)
    pickler.save_reduce(_create_lock, (obj.locked(),), obj=obj)
    logger.trace(pickler, "# Lo")
    return

@register(RLockType)
def save_rlock(pickler, obj):
    logger.trace(pickler, "RL: %s", obj)
    r = obj.__repr__() # don't use _release_save as it unlocks the lock
    count = int(r.split('count=')[1].split()[0].rstrip('>'))
    owner = int(r.split('owner=')[1].split()[0])
    pickler.save_reduce(_create_rlock, (count,owner,), obj=obj)
    logger.trace(pickler, "# RL")
    return

#@register(SocketType) #FIXME: causes multiprocess test_pickling FAIL
def save_socket(pickler, obj):
    logger.trace(pickler, "So: %s", obj)
    pickler.save_reduce(*reduce_socket(obj))
    logger.trace(pickler, "# So")
    return

def _save_file(pickler, obj, open_):
    if obj.closed:
        position = 0
    else:
        obj.flush()
        if obj in (sys.__stdout__, sys.__stderr__, sys.__stdin__):
            position = -1
        else:
            position = obj.tell()
    if is_dill(pickler, child=True) and pickler._fmode == FILE_FMODE:
        f = open_(obj.name, "r")
        fdata = f.read()
        f.close()
    else:
        fdata = ""
    if is_dill(pickler, child=True):
        strictio = pickler._strictio
        fmode = pickler._fmode
    else:
        strictio = False
        fmode = 0 # HANDLE_FMODE
    pickler.save_reduce(_create_filehandle, (obj.name, obj.mode, position,
                                             obj.closed, open_, strictio,
                                             fmode, fdata), obj=obj)
    return


@register(FileType) #XXX: in 3.x has buffer=0, needs different _create?
@register(BufferedRandomType)
@register(BufferedReaderType)
@register(BufferedWriterType)
@register(TextWrapperType)
def save_file(pickler, obj):
    logger.trace(pickler, "Fi: %s", obj)
    f = _save_file(pickler, obj, open)
    logger.trace(pickler, "# Fi")
    return f

if PyTextWrapperType:
    @register(PyBufferedRandomType)
    @register(PyBufferedReaderType)
    @register(PyBufferedWriterType)
    @register(PyTextWrapperType)
    def save_file(pickler, obj):
        logger.trace(pickler, "Fi: %s", obj)
        f = _save_file(pickler, obj, _open)
        logger.trace(pickler, "# Fi")
        return f

# The following two functions are based on 'saveCStringIoInput'
# and 'saveCStringIoOutput' from spickle
# Copyright (c) 2011 by science+computing ag
# License: http://www.apache.org/licenses/LICENSE-2.0
if InputType:
    @register(InputType)
    def save_stringi(pickler, obj):
        logger.trace(pickler, "Io: %s", obj)
        if obj.closed:
            value = ''; position = 0
        else:
            value = obj.getvalue(); position = obj.tell()
        pickler.save_reduce(_create_stringi, (value, position, \
                                              obj.closed), obj=obj)
        logger.trace(pickler, "# Io")
        return

    @register(OutputType)
    def save_stringo(pickler, obj):
        logger.trace(pickler, "Io: %s", obj)
        if obj.closed:
            value = ''; position = 0
        else:
            value = obj.getvalue(); position = obj.tell()
        pickler.save_reduce(_create_stringo, (value, position, \
                                              obj.closed), obj=obj)
        logger.trace(pickler, "# Io")
        return

if LRUCacheType is not None:
    from functools import lru_cache
    @register(LRUCacheType)
    def save_lru_cache(pickler, obj):
        logger.trace(pickler, "LRU: %s", obj)
        if OLD39:
            kwargs = obj.cache_info()
            args = (kwargs.maxsize,)
        else:
            kwargs = obj.cache_parameters()
            args = (kwargs['maxsize'], kwargs['typed'])
        if args != lru_cache.__defaults__:
            wrapper = Reduce(lru_cache, args, is_callable=True)
        else:
            wrapper = lru_cache
        pickler.save_reduce(wrapper, (obj.__wrapped__,), obj=obj)
        logger.trace(pickler, "# LRU")
        return

@register(SuperType)
def save_super(pickler, obj):
    logger.trace(pickler, "Su: %s", obj)
    pickler.save_reduce(super, (obj.__thisclass__, obj.__self__), obj=obj)
    logger.trace(pickler, "# Su")
    return

if IS_PYPY:
    @register(MethodType)
    def save_instancemethod0(pickler, obj):
        code = getattr(obj.__func__, '__code__', None)
        if code is not None and type(code) is not CodeType \
              and getattr(obj.__self__, obj.__name__) == obj:
            # Some PyPy builtin functions have no module name
            logger.trace(pickler, "Me2: %s", obj)
            # TODO: verify that this works for all PyPy builtin methods
            pickler.save_reduce(getattr, (obj.__self__, obj.__name__), obj=obj)
            logger.trace(pickler, "# Me2")
            return

        logger.trace(pickler, "Me1: %s", obj)
        pickler.save_reduce(MethodType, (obj.__func__, obj.__self__), obj=obj)
        logger.trace(pickler, "# Me1")
        return
else:
    @register(MethodType)
    def save_instancemethod0(pickler, obj):
        logger.trace(pickler, "Me1: %s", obj)
        pickler.save_reduce(MethodType, (obj.__func__, obj.__self__), obj=obj)
        logger.trace(pickler, "# Me1")
        return

if not IS_PYPY:
    @register(MemberDescriptorType)
    @register(GetSetDescriptorType)
    @register(MethodDescriptorType)
    @register(WrapperDescriptorType)
    @register(ClassMethodDescriptorType)
    def save_wrapper_descriptor(pickler, obj):
        logger.trace(pickler, "Wr: %s", obj)
        pickler.save_reduce(_getattr, (obj.__objclass__, obj.__name__,
                                       obj.__repr__()), obj=obj)
        logger.trace(pickler, "# Wr")
        return
else:
    @register(MemberDescriptorType)
    @register(GetSetDescriptorType)
    def save_wrapper_descriptor(pickler, obj):
        logger.trace(pickler, "Wr: %s", obj)
        pickler.save_reduce(_getattr, (obj.__objclass__, obj.__name__,
                                       obj.__repr__()), obj=obj)
        logger.trace(pickler, "# Wr")
        return

@register(CellType)
def save_cell(pickler, obj):
    try:
        f = obj.cell_contents
    except ValueError: # cell is empty
        logger.trace(pickler, "Ce3: %s", obj)
        # _shims._CELL_EMPTY is defined in _shims.py to support PyPy 2.7.
        # It unpickles to a sentinel object _dill._CELL_EMPTY, also created in
        # _shims.py. This object is not present in Python 3 because the cell's
        # contents can be deleted in newer versions of Python. The reduce object
        # will instead unpickle to None if unpickled in Python 3.

        # When breaking changes are made to dill, (_shims._CELL_EMPTY,) can
        # be replaced by () OR the delattr function can be removed repending on
        # whichever is more convienient.
        pickler.save_reduce(_create_cell, (_shims._CELL_EMPTY,), obj=obj)
        # Call the function _delattr on the cell's cell_contents attribute
        # The result of this function call will be None
        pickler.save_reduce(_shims._delattr, (obj, 'cell_contents'))
        # pop None created by calling _delattr off stack
        pickler.write(bytes('0', 'UTF-8'))
        logger.trace(pickler, "# Ce3")
        return
    if is_dill(pickler, child=True):
        if id(f) in pickler._postproc:
            # Already seen. Add to its postprocessing.
            postproc = pickler._postproc[id(f)]
        else:
            # Haven't seen it. Add to the highest possible object and set its
            # value as late as possible to prevent cycle.
            postproc = next(iter(pickler._postproc.values()), None)
        if postproc is not None:
            logger.trace(pickler, "Ce2: %s", obj)
            # _CELL_REF is defined in _shims.py to support older versions of
            # dill. When breaking changes are made to dill, (_CELL_REF,) can
            # be replaced by ()
            pickler.save_reduce(_create_cell, (_CELL_REF,), obj=obj)
            postproc.append((_shims._setattr, (obj, 'cell_contents', f)))
            logger.trace(pickler, "# Ce2")
            return
    logger.trace(pickler, "Ce1: %s", obj)
    pickler.save_reduce(_create_cell, (f,), obj=obj)
    logger.trace(pickler, "# Ce1")
    return

if MAPPING_PROXY_TRICK:
    @register(DictProxyType)
    def save_dictproxy(pickler, obj):
        logger.trace(pickler, "Mp: %s", _repr_dict(obj)) # obj
        mapping = obj | _dictproxy_helper_instance
        pickler.save_reduce(DictProxyType, (mapping,), obj=obj)
        logger.trace(pickler, "# Mp")
        return
else:
    @register(DictProxyType)
    def save_dictproxy(pickler, obj):
        logger.trace(pickler, "Mp: %s", _repr_dict(obj)) # obj
        pickler.save_reduce(DictProxyType, (obj.copy(),), obj=obj)
        logger.trace(pickler, "# Mp")
        return

@register(SliceType)
def save_slice(pickler, obj):
    logger.trace(pickler, "Sl: %s", obj)
    pickler.save_reduce(slice, (obj.start, obj.stop, obj.step), obj=obj)
    logger.trace(pickler, "# Sl")
    return

@register(XRangeType)
@register(EllipsisType)
@register(NotImplementedType)
def save_singleton(pickler, obj):
    logger.trace(pickler, "Si: %s", obj)
    pickler.save_reduce(_eval_repr, (obj.__repr__(),), obj=obj)
    logger.trace(pickler, "# Si")
    return

def _proxy_helper(obj): # a dead proxy returns a reference to None
    """get memory address of proxy's reference object"""
    _repr = repr(obj)
    try: _str = str(obj)
    except ReferenceError: # it's a dead proxy
        return id(None)
    if _str == _repr: return id(obj) # it's a repr
    try: # either way, it's a proxy from here
        address = int(_str.rstrip('>').split(' at ')[-1], base=16)
    except ValueError: # special case: proxy of a 'type'
        if not IS_PYPY:
            address = int(_repr.rstrip('>').split(' at ')[-1], base=16)
        else:
            objects = iter(gc.get_objects())
            for _obj in objects:
                if repr(_obj) == _str: return id(_obj)
            # all bad below... nothing found so throw ReferenceError
            msg = "Cannot reference object for proxy at '%s'" % id(obj)
            raise ReferenceError(msg)
    return address

def _locate_object(address, module=None):
    """get object located at the given memory address (inverse of id(obj))"""
    special = [None, True, False] #XXX: more...?
    for obj in special:
        if address == id(obj): return obj
    if module:
        objects = iter(module.__dict__.values())
    else: objects = iter(gc.get_objects())
    for obj in objects:
        if address == id(obj): return obj
    # all bad below... nothing found so throw ReferenceError or TypeError
    try: address = hex(address)
    except TypeError:
        raise TypeError("'%s' is not a valid memory address" % str(address))
    raise ReferenceError("Cannot reference object at '%s'" % address)

@register(ReferenceType)
def save_weakref(pickler, obj):
    refobj = obj()
    logger.trace(pickler, "R1: %s", obj)
   #refobj = ctypes.pythonapi.PyWeakref_GetObject(obj) # dead returns "None"
    pickler.save_reduce(_create_weakref, (refobj,), obj=obj)
    logger.trace(pickler, "# R1")
    return

@register(ProxyType)
@register(CallableProxyType)
def save_weakproxy(pickler, obj):
    refobj = _locate_object(_proxy_helper(obj))
    try:
        _t = "R2"
        logger.trace(pickler, "%s: %s", _t, obj)
    except ReferenceError:
        _t = "R3"
        logger.trace(pickler, "%s: %s", _t, sys.exc_info()[1])
   #callable = bool(getattr(refobj, '__call__', None))
    if type(obj) is CallableProxyType: callable = True
    else: callable = False
    pickler.save_reduce(_create_weakproxy, (refobj, callable), obj=obj)
    logger.trace(pickler, "# %s", _t)
    return

def _is_builtin_module(module):
    if not hasattr(module, "__file__"): return True
    # If a module file name starts with prefix, it should be a builtin
    # module, so should always be pickled as a reference.
    names = ["base_prefix", "base_exec_prefix", "exec_prefix", "prefix", "real_prefix"]
    return any(os.path.realpath(module.__file__).startswith(os.path.realpath(getattr(sys, name)))
               for name in names if hasattr(sys, name)) or \
            module.__file__.endswith(EXTENSION_SUFFIXES) or \
            'site-packages' in module.__file__

def _is_imported_module(module):
    return getattr(module, '__loader__', None) is not None or module in sys.modules.values()

@register(ModuleType)
def save_module(pickler, obj):
    if False: #_use_diff:
        if obj.__name__.split('.', 1)[0] != "dill":
            try:
                changed = diff.whats_changed(obj, seen=pickler._diff_cache)[0]
            except RuntimeError:  # not memorised module, probably part of dill
                pass
            else:
                logger.trace(pickler, "M2: %s with diff", obj)
                logger.trace(pickler, "Diff: %s", changed.keys())
                pickler.save_reduce(_import_module, (obj.__name__,), obj=obj,
                                    state=changed)
                logger.trace(pickler, "# M2")
                return

        logger.trace(pickler, "M1: %s", obj)
        pickler.save_reduce(_import_module, (obj.__name__,), obj=obj)
        logger.trace(pickler, "# M1")
    else:
        builtin_mod = _is_builtin_module(obj)
        if obj.__name__ not in ("builtins", "dill", "dill._dill") and not builtin_mod or \
                is_dill(pickler, child=True) and obj is pickler._main:
            logger.trace(pickler, "M1: %s", obj)
            _main_dict = obj.__dict__.copy() #XXX: better no copy? option to copy?
            [_main_dict.pop(item, None) for item in singletontypes
                + ["__builtins__", "__loader__"]]
            mod_name = obj.__name__ if _is_imported_module(obj) else '__runtime__.%s' % obj.__name__
            pickler.save_reduce(_import_module, (mod_name,), obj=obj,
                                state=_main_dict)
            logger.trace(pickler, "# M1")
        elif obj.__name__ == "dill._dill":
            logger.trace(pickler, "M2: %s", obj)
            pickler.save_global(obj, name="_dill")
            logger.trace(pickler, "# M2")
        else:
            logger.trace(pickler, "M2: %s", obj)
            pickler.save_reduce(_import_module, (obj.__name__,), obj=obj)
            logger.trace(pickler, "# M2")
        return
    return

@register(TypeType)
def save_type(pickler, obj, postproc_list=None):
    if obj in _typemap:
        logger.trace(pickler, "T1: %s", obj)
        # if obj in _incedental_types:
        #     warnings.warn('Type %r may only exist on this implementation of Python and cannot be unpickled in other implementations.' % (obj,), PicklingWarning)
        pickler.save_reduce(_load_type, (_typemap[obj],), obj=obj)
        logger.trace(pickler, "# T1")
    elif obj.__bases__ == (tuple,) and all([hasattr(obj, attr) for attr in ('_fields','_asdict','_make','_replace')]):
        # special case: namedtuples
        logger.trace(pickler, "T6: %s", obj)
        if not obj._field_defaults:
            pickler.save_reduce(_create_namedtuple, (obj.__name__, obj._fields, obj.__module__), obj=obj)
        else:
            defaults = [obj._field_defaults[field] for field in obj._fields if field in obj._field_defaults]
            pickler.save_reduce(_create_namedtuple, (obj.__name__, obj._fields, obj.__module__, defaults), obj=obj)
        logger.trace(pickler, "# T6")
        return

    # special cases: NoneType, NotImplementedType, EllipsisType
    elif obj is type(None):
        logger.trace(pickler, "T7: %s", obj)
        #XXX: pickler.save_reduce(type, (None,), obj=obj)
        pickler.write(bytes('c__builtin__\nNoneType\n', 'UTF-8'))
        logger.trace(pickler, "# T7")
    elif obj is NotImplementedType:
        logger.trace(pickler, "T7: %s", obj)
        pickler.save_reduce(type, (NotImplemented,), obj=obj)
        logger.trace(pickler, "# T7")
    elif obj is EllipsisType:
        logger.trace(pickler, "T7: %s", obj)
        pickler.save_reduce(type, (Ellipsis,), obj=obj)
        logger.trace(pickler, "# T7")

    else:
        obj_name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
        _byref = getattr(pickler, '_byref', None)
        obj_recursive = id(obj) in getattr(pickler, '_postproc', ())
        incorrectly_named = not _locate_function(obj, pickler)
        if not _byref and not obj_recursive and incorrectly_named: # not a function, but the name was held over
            if issubclass(type(obj), type):
                # thanks to Tom Stepleton pointing out pickler._session unneeded
                _t = 'T2'
                logger.trace(pickler, "%s: %s", _t, obj)
                _dict = _dict_from_dictproxy(obj.__dict__)
            else:
                _t = 'T3'
                logger.trace(pickler, "%s: %s", _t, obj)
                _dict = obj.__dict__
           #print (_dict)
           #print ("%s\n%s" % (type(obj), obj.__name__))
           #print ("%s\n%s" % (obj.__bases__, obj.__dict__))
            for name in _dict.get("__slots__", []):
                del _dict[name]
            if obj_name != obj.__name__:
                if postproc_list is None:
                    postproc_list = []
                postproc_list.append((setattr, (obj, '__qualname__', obj_name)))
            _save_with_postproc(pickler, (_create_type, (
                type(obj), obj.__name__, obj.__bases__, _dict
            )), obj=obj, postproc_list=postproc_list)
            logger.trace(pickler, "# %s", _t)
        else:
            logger.trace(pickler, "T4: %s", obj)
            if incorrectly_named:
                warnings.warn('Cannot locate reference to %r.' % (obj,), PicklingWarning)
            if obj_recursive:
                warnings.warn('Cannot pickle %r: %s.%s has recursive self-references that trigger a RecursionError.' % (obj, obj.__module__, obj_name), PicklingWarning)
           #print (obj.__dict__)
           #print ("%s\n%s" % (type(obj), obj.__name__))
           #print ("%s\n%s" % (obj.__bases__, obj.__dict__))
            StockPickler.save_global(pickler, obj, name=obj_name)
            logger.trace(pickler, "# T4")
    return

@register(property)
def save_property(pickler, obj):
    logger.trace(pickler, "Pr: %s", obj)
    pickler.save_reduce(property, (obj.fget, obj.fset, obj.fdel, obj.__doc__),
                        obj=obj)
    logger.trace(pickler, "# Pr")

@register(staticmethod)
@register(classmethod)
def save_classmethod(pickler, obj):
    logger.trace(pickler, "Cm: %s", obj)
    orig_func = obj.__func__

    # if type(obj.__dict__) is dict:
    #     if obj.__dict__:
    #         state = obj.__dict__
    #     else:
    #         state = None
    # else:
    #     state = (None, {'__dict__', obj.__dict__})

    pickler.save_reduce(type(obj), (orig_func,), obj=obj)
    logger.trace(pickler, "# Cm")

@register(FunctionType)
def save_function(pickler, obj):
    if not _locate_function(obj, pickler):
        if type(obj.__code__) is not CodeType:
            # Some PyPy builtin functions have no module name, and thus are not
            # able to be located
            module_name = getattr(obj, '__module__', None)
            if module_name is None:
                module_name = __builtin__.__name__
            module = _import_module(module_name, safe=True)
            _pypy_builtin = False
            try:
                found, _ = _getattribute(module, obj.__qualname__)
                if getattr(found, '__func__', None) is obj:
                    _pypy_builtin = True
            except AttributeError:
                pass

            if _pypy_builtin:
                logger.trace(pickler, "F3: %s", obj)
                pickler.save_reduce(getattr, (found, '__func__'), obj=obj)
                logger.trace(pickler, "# F3")
                return

        logger.trace(pickler, "F1: %s", obj)
        _recurse = getattr(pickler, '_recurse', None)
        _postproc = getattr(pickler, '_postproc', None)
        _main_modified = getattr(pickler, '_main_modified', None)
        _original_main = getattr(pickler, '_original_main', __builtin__)#'None'
        postproc_list = []
        if _recurse:
            # recurse to get all globals referred to by obj
            from .detect import globalvars
            globs_copy = globalvars(obj, recurse=True, builtin=True)

            # Add the name of the module to the globs dictionary to prevent
            # the duplication of the dictionary. Pickle the unpopulated
            # globals dictionary and set the remaining items after the function
            # is created to correctly handle recursion.
            globs = {'__name__': obj.__module__}
        else:
            globs_copy = obj.__globals__

            # If the globals is the __dict__ from the module being saved as a
            # session, substitute it by the dictionary being actually saved.
            if _main_modified and globs_copy is _original_main.__dict__:
                globs_copy = getattr(pickler, '_main', _original_main).__dict__
                globs = globs_copy
            # If the globals is a module __dict__, do not save it in the pickle.
            elif globs_copy is not None and obj.__module__ is not None and \
                    getattr(_import_module(obj.__module__, True), '__dict__', None) is globs_copy:
                globs = globs_copy
            else:
                globs = {'__name__': obj.__module__}

        if globs_copy is not None and globs is not globs_copy:
            # In the case that the globals are copied, we need to ensure that
            # the globals dictionary is updated when all objects in the
            # dictionary are already created.
            glob_ids = {id(g) for g in globs_copy.values()}
            for stack_element in _postproc:
                if stack_element in glob_ids:
                    _postproc[stack_element].append((_setitems, (globs, globs_copy)))
                    break
            else:
                postproc_list.append((_setitems, (globs, globs_copy)))

        closure = obj.__closure__
        state_dict = {}
        for fattrname in ('__doc__', '__kwdefaults__', '__annotations__'):
            fattr = getattr(obj, fattrname, None)
            if fattr is not None:
                state_dict[fattrname] = fattr
        if obj.__qualname__ != obj.__name__:
            state_dict['__qualname__'] = obj.__qualname__
        if '__name__' not in globs or obj.__module__ != globs['__name__']:
            state_dict['__module__'] = obj.__module__

        state = obj.__dict__
        if type(state) is not dict:
            state_dict['__dict__'] = state
            state = None
        if state_dict:
            state = state, state_dict

        _save_with_postproc(pickler, (_create_function, (
                obj.__code__, globs, obj.__name__, obj.__defaults__,
                closure
        ), state), obj=obj, postproc_list=postproc_list)

        # Lift closure cell update to earliest function (#458)
        if _postproc:
            topmost_postproc = next(iter(_postproc.values()), None)
            if closure and topmost_postproc:
                for cell in closure:
                    possible_postproc = (setattr, (cell, 'cell_contents', obj))
                    try:
                        topmost_postproc.remove(possible_postproc)
                    except ValueError:
                        continue

                    # Change the value of the cell
                    pickler.save_reduce(*possible_postproc)
                    # pop None created by calling preprocessing step off stack
                    pickler.write(bytes('0', 'UTF-8'))

        logger.trace(pickler, "# F1")
    else:
        logger.trace(pickler, "F2: %s", obj)
        name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
        StockPickler.save_global(pickler, obj, name=name)
        logger.trace(pickler, "# F2")
    return

if HAS_CTYPES and hasattr(ctypes, 'pythonapi'):
    _PyCapsule_New = ctypes.pythonapi.PyCapsule_New
    _PyCapsule_New.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)
    _PyCapsule_New.restype = ctypes.py_object
    _PyCapsule_GetPointer = ctypes.pythonapi.PyCapsule_GetPointer
    _PyCapsule_GetPointer.argtypes = (ctypes.py_object, ctypes.c_char_p)
    _PyCapsule_GetPointer.restype = ctypes.c_void_p
    _PyCapsule_GetDestructor = ctypes.pythonapi.PyCapsule_GetDestructor
    _PyCapsule_GetDestructor.argtypes = (ctypes.py_object,)
    _PyCapsule_GetDestructor.restype = ctypes.c_void_p
    _PyCapsule_GetContext = ctypes.pythonapi.PyCapsule_GetContext
    _PyCapsule_GetContext.argtypes = (ctypes.py_object,)
    _PyCapsule_GetContext.restype = ctypes.c_void_p
    _PyCapsule_GetName = ctypes.pythonapi.PyCapsule_GetName
    _PyCapsule_GetName.argtypes = (ctypes.py_object,)
    _PyCapsule_GetName.restype = ctypes.c_char_p
    _PyCapsule_IsValid = ctypes.pythonapi.PyCapsule_IsValid
    _PyCapsule_IsValid.argtypes = (ctypes.py_object, ctypes.c_char_p)
    _PyCapsule_IsValid.restype = ctypes.c_bool
    _PyCapsule_SetContext = ctypes.pythonapi.PyCapsule_SetContext
    _PyCapsule_SetContext.argtypes = (ctypes.py_object, ctypes.c_void_p)
    _PyCapsule_SetDestructor = ctypes.pythonapi.PyCapsule_SetDestructor
    _PyCapsule_SetDestructor.argtypes = (ctypes.py_object, ctypes.c_void_p)
    _PyCapsule_SetName = ctypes.pythonapi.PyCapsule_SetName
    _PyCapsule_SetName.argtypes = (ctypes.py_object, ctypes.c_char_p)
    _PyCapsule_SetPointer = ctypes.pythonapi.PyCapsule_SetPointer
    _PyCapsule_SetPointer.argtypes = (ctypes.py_object, ctypes.c_void_p)
    _testcapsule = _PyCapsule_New(
        ctypes.cast(_PyCapsule_New, ctypes.c_void_p),
        ctypes.create_string_buffer(b'dill._dill._testcapsule'),
        None
    )
    PyCapsuleType = type(_testcapsule)
    @register(PyCapsuleType)
    def save_capsule(pickler, obj):
        logger.trace(pickler, "Cap: %s", obj)
        name = _PyCapsule_GetName(obj)
        warnings.warn('Pickling a PyCapsule (%s) does not pickle any C data structures and could cause segmentation faults or other memory errors when unpickling.' % (name,), PicklingWarning)
        pointer = _PyCapsule_GetPointer(obj, name)
        context = _PyCapsule_GetContext(obj)
        destructor = _PyCapsule_GetDestructor(obj)
        pickler.save_reduce(_create_capsule, (pointer, name, context, destructor), obj=obj)
        logger.trace(pickler, "# Cap")
    _incedental_reverse_typemap['PyCapsuleType'] = PyCapsuleType
    _reverse_typemap['PyCapsuleType'] = PyCapsuleType
    _incedental_types.add(PyCapsuleType)
else:
    _testcapsule = None

# quick sanity checking
def pickles(obj,exact=False,safe=False,**kwds):
    """
    Quick check if object pickles with dill.

    If *exact=True* then an equality test is done to check if the reconstructed
    object matches the original object.

    If *safe=True* then any exception will raised in copy signal that the
    object is not picklable, otherwise only pickling errors will be trapped.

    Additional keyword arguments are as :func:`dumps` and :func:`loads`.
    """
    if safe: exceptions = (Exception,) # RuntimeError, ValueError
    else:
        exceptions = (TypeError, AssertionError, PicklingError, UnpicklingError)
    try:
        pik = copy(obj, **kwds)
        #FIXME: should check types match first, then check content if "exact"
        try:
            #FIXME: should be "(pik == obj).all()" for numpy comparison, though that'll fail if shapes differ
            result = bool(pik.all() == obj.all())
        except AttributeError:
            warnings.filterwarnings('ignore')
            result = pik == obj
            warnings.resetwarnings()
        if hasattr(result, 'toarray'): # for unusual types like sparse matrix
            result = result.toarray().all()
        if result: return True
        if not exact:
            result = type(pik) == type(obj)
            if result: return result
            # class instances might have been dumped with byref=False
            return repr(type(pik)) == repr(type(obj)) #XXX: InstanceType?
        return False
    except exceptions:
        return False

def check(obj, *args, **kwds):
    """
    Check pickling of an object across another process.

    *python* is the path to the python interpreter (defaults to sys.executable)

    Set *verbose=True* to print the unpickled object in the other process.

    Additional keyword arguments are as :func:`dumps` and :func:`loads`.
    """
   # == undocumented ==
   # python -- the string path or executable name of the selected python
   # verbose -- if True, be verbose about printing warning messages
   # all other args and kwds are passed to dill.dumps #FIXME: ignore on load
    verbose = kwds.pop('verbose', False)
    python = kwds.pop('python', None)
    if python is None:
        import sys
        python = sys.executable
    # type check
    isinstance(python, str)
    import subprocess
    fail = True
    try:
        _obj = dumps(obj, *args, **kwds)
        fail = False
    finally:
        if fail and verbose:
            print("DUMP FAILED")
    #FIXME: fails if python interpreter path contains spaces
    # Use the following instead (which also processes the 'ignore' keyword):
    #    ignore = kwds.pop('ignore', None)
    #    unpickle = "dill.loads(%s, ignore=%s)"%(repr(_obj), repr(ignore))
    #    cmd = [python, "-c", "import dill; print(%s)"%unpickle]
    #    msg = "SUCCESS" if not subprocess.call(cmd) else "LOAD FAILED"
    msg = "%s -c import dill; print(dill.loads(%s))" % (python, repr(_obj))
    msg = "SUCCESS" if not subprocess.call(msg.split(None,2)) else "LOAD FAILED"
    if verbose:
        print(msg)
    return

# use to protect against missing attributes
def is_dill(pickler, child=None):
    "check the dill-ness of your pickler"
    if child is False or not hasattr(pickler.__class__, 'mro'):
        return 'dill' in pickler.__module__
    return Pickler in pickler.__class__.mro()

def _extend():
    """extend pickle with all of dill's registered types"""
    # need to have pickle not choke on _main_module?  use is_dill(pickler)
    for t,func in Pickler.dispatch.items():
        try:
            StockPickler.dispatch[t] = func
        except Exception: #TypeError, PicklingError, UnpicklingError
            logger.trace(pickler, "skip: %s", t)
    return

del diff, _use_diff, use_diff

# EOF
