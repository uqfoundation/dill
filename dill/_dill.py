# -*- coding: utf-8 -*-
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2015 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
dill: a utility for serialization of python objects

The main API of the package are the functions :func:`dump` and
:func:`dumps` for serialization ("pickling"), and :func:`load`
and :func:`loads` for deserialization ("unpickling").  The
functions :func:`~dill.session.dump_module` and
:func:`~dill.session.load_module` can be used to save and restore
the intepreter session.

Based on code written by Oren Tirosh and Armin Ronacher.
Extended to a (near) full set of the builtin types (in types module),
and coded to the pickle interface, by <mmckerns@caltech.edu>.
Initial port to python3 by Jonathan Dobson, continued by mmckerns.
Test against "all" python types (Std. Lib. CH 1-15 @ 2.7) by mmckerns.
Test against CH16+ Std. Lib. ... TBD.
"""

from __future__ import annotations

__all__ = [
    'dump','dumps','load','loads','copy',
    'Pickler','Unpickler','register','pickle','pickles','check',
    'DEFAULT_PROTOCOL','HIGHEST_PROTOCOL','HANDLE_FMODE','CONTENTS_FMODE','FILE_FMODE',
    'PickleError','PickleWarning','PicklingError','PicklingWarning','UnpicklingError',
    'UnpicklingWarning',
]

__module__ = 'dill'

import warnings
from dill import logging
from .logging import adapter as logger
from .logging import trace as _trace

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
from pickle import DICT, GLOBAL, MARK, POP, SETITEM
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
import dataclasses
import weakref
from weakref import ReferenceType, ProxyType, CallableProxyType
from collections import OrderedDict
from functools import partial, wraps
from operator import itemgetter, attrgetter
GENERATOR_FAIL = False
import importlib.machinery
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
    def ndarraysubclassinstance(obj_type):
        if all((c.__module__, c.__name__) != ('numpy', 'ndarray') for c in obj_type.__mro__):
            return False
        # anything below here is a numpy array (or subclass) instance
        __hook__() # import numpy (so the following works!!!)
        # verify that __reduce__ has not been overridden
        if obj_type.__reduce_ex__ is not NumpyArrayType.__reduce_ex__ \
                or obj_type.__reduce__ is not NumpyArrayType.__reduce__:
            return False
        return True
    def numpyufunc(obj_type):
        return any((c.__module__, c.__name__) == ('numpy', 'ufunc') for c in obj_type.__mro__)
    def numpydtype(obj_type):
        if all((c.__module__, c.__name__) != ('numpy', 'dtype') for c in obj_type.__mro__):
            return False
        # anything below here is a numpy dtype
        __hook__() # import numpy (so the following works!!!)
        return obj_type is type(NumpyDType) # handles subclasses
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
try: #pragma: no cover
    IS_IPYTHON = __IPYTHON__  # is True
    ExitType = None # IPython.core.autocall.ExitAutocall
    IPYTHON_SINGLETONS = ('exit', 'quit', 'get_ipython')
except NameError:
    IS_IPYTHON = False
    try: ExitType = type(exit) # apparently 'exit' can be removed
    except NameError: ExitType = None
    IPYTHON_SINGLETONS = ()

import inspect
import typing


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

# Exceptions commonly raised by unpickleable objects in the Standard Library.
UNPICKLEABLE_ERRORS = (PicklingError, TypeError, ValueError, NotImplementedError)

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
    protocol = int(_getopt(settings, 'protocol', protocol))
    kwds.update(byref=byref, fmode=fmode, recurse=recurse)
    Pickler(file, protocol, **kwds).dump(obj)
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

def _getopt(settings, key, arg=None, *, kwds=None):
    """Get option from named argument 'arg' or 'kwds', falling back to settings.

    Examples:

        # With an explicitly named argument:
        protocol = int(_getopt(settings, 'protocol', protocol))

        # With a named argument in **kwds:
        self._byref = _getopt(settings, 'byref', kwds=kwds)
    """
    # Sanity check, it's a bug in calling code if False.
    assert kwds is None or arg is None
    if kwds is not None:
        arg = kwds.pop(key, None)
    if arg is not None:
        return arg
    else:
        return settings[key]

### Extend the Picklers
class Pickler(StockPickler):
    """python's Pickler extended to interpreter sessions"""
    dispatch: typing.Dict[type, typing.Callable[[Pickler, typing.Any], None]] \
            = MetaCatchingDict(StockPickler.dispatch.copy())
    """The dispatch table, a dictionary of serializing functions used
    by Pickler to save objects of specific types.  Use :func:`pickle`
    or :func:`register` to associate types to custom functions.

    :meta hide-value:
    """
    from .settings import settings
    # Flags set by dump_module() is dill.session:
    _refimported = False
    _refonfail = False
    _session = False
    _first_pass = False

    def __init__(self, file, *args, **kwds):
        settings = Pickler.settings
        self._main = _main_module
        self._diff_cache = {}
        self._byref = _getopt(settings, 'byref', kwds=kwds)
        self._fmode = _getopt(settings, 'fmode', kwds=kwds)
        self._recurse = _getopt(settings, 'recurse', kwds=kwds)
        self._strictio = False #_getopt(settings, 'strictio', kwds=kwds)
        self._postproc = OrderedDict()
        self._file_tell = getattr(file, 'tell', None)  # for logger and refonfail
        StockPickler.__init__(self, file, *args, **kwds)

    def save(self, obj, save_persistent_id=True):
        # This method overrides StockPickler.save() and is called for every
        # object pickled.  When 'refonfail' is True, it tries to save the object
        # by reference if pickling it fails with a common pickling error, as
        # defined by the constant UNPICKLEABLE_ERRORS.  If that also fails, then
        # the exception is raised and, if this method was called indirectly from
        # another Pickler.save() call, the parent objects will try to be saved
        # by reference recursively, until it succeeds or the exception
        # propagates beyond the topmost save() call.

        # numpy hack
        obj_type = type(obj)
        if NumpyArrayType and not (obj_type is type or obj_type in Pickler.dispatch):
            # register if the object is a numpy ufunc
            # thanks to Paul Kienzle for pointing out ufuncs didn't pickle
            if numpyufunc(obj_type):
                @register(obj_type)
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
            if numpydtype(obj_type):
                @register(obj_type)
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
            if ndarraysubclassinstance(obj_type):
                @register(obj_type)
                def save_numpy_array(pickler, obj):
                    logger.trace(pickler, "Nu: (%s, %s)", obj.shape, obj.dtype, obj=obj)
                    npdict = getattr(obj, '__dict__', None)
                    f, args, state = obj.__reduce__()
                    pickler.save_reduce(_create_array, (f,args,state,npdict), obj=obj)
                    logger.trace(pickler, "# Nu")
                    return
        # end numpy hack

        if GENERATOR_FAIL and obj_type is GeneratorType:
            msg = "Can't pickle %s: attribute lookup builtins.generator failed" % GeneratorType
            raise PicklingError(msg)

        if not self._refonfail:
            StockPickler.save(self, obj, save_persistent_id)
            return

        ## Save with 'refonfail' ##

        # Disable framing. This must be set right after the
        # framer.init_framing() call at StockPickler.dump()).
        self.framer.current_frame = None
        # Store initial state.
        position = self._file_tell()
        memo_size = len(self.memo)
        try:
            StockPickler.save(self, obj, save_persistent_id)
        except UNPICKLEABLE_ERRORS as error_stack:
            trace_message = (
                "# X: fallback to save as global: <%s object at %#012x>"
                % (type(obj).__name__, id(obj))
            )
            # Roll back the stream. Note: truncate(position) doesn't always work.
            self._file_seek(position)
            self._file_truncate()
            # Roll back memo.
            for _ in range(len(self.memo) - memo_size):
                self.memo.popitem()  # LIFO order is guaranteed since 3.7
            # Handle session main.
            if self._session and obj is self._main:
                if self._main is _main_module or not _is_imported_module(self._main):
                    raise
                # Save an empty dict as state to distinguish from modules saved with dump().
                self.save_reduce(_import_module, (obj.__name__,), obj=obj, state={})
                logger.trace(self, trace_message, obj=obj)
                warnings.warn(
                    "module %r saved by reference due to the unpickleable "
                    "variable %r. No changes to the module were saved. "
                    "Unpickleable variables can be ignored with filters."
                    % (self._main.__name__, error_stack.name),
                    PicklingWarning,
                    stacklevel=5,
                )
            # Try to save object by reference.
            elif hasattr(obj, '__name__') or hasattr(obj, '__qualname__'):
                try:
                    self.save_global(obj)
                    logger.trace(self, trace_message, obj=obj)
                    return True  # for _saved_byref, ignored otherwise
                except PicklingError as error:
                    # Roll back trace state.
                    logger.roll_back(self, obj)
                    raise error from error_stack
            else:
                # Roll back trace state.
                logger.roll_back(self, obj)
                raise
        return
    save.__doc__ = StockPickler.save.__doc__

    def dump(self, obj): #NOTE: if settings change, need to update attributes
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
        self._main = _main_module
        self._ignore = _getopt(settings, 'ignore', kwds=kwds)
        StockUnpickler.__init__(self, *args, **kwds)

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
    """expose :attr:`~Pickler.dispatch` table for user-created extensions"""
    Pickler.dispatch[t] = func
    return

def register(t):
    """decorator to register types to Pickler's :attr:`~Pickler.dispatch` table"""
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
    Also helps avoid some unpickleable objects.
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
    'PartialType': PartialType,
    'SuperType': SuperType,
    'ItemGetterType': ItemGetterType,
    'AttrGetterType': AttrGetterType,
})
if sys.hexversion < 0x30800a2:
    _reverse_typemap.update({
        'CellType': CellType,
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

if sys.hexversion >= 0x30a00a0:
    _incedental_reverse_typemap['LineIteratorType'] = type(compile('3', '', 'eval').co_lines())
'''

if sys.hexversion >= 0x30b00b0:
    from types import GenericAlias
    _incedental_reverse_typemap["GenericAliasIteratorType"] = type(iter(GenericAlias(list, (int,))))
    '''
    _incedental_reverse_typemap['PositionsIteratorType'] = type(compile('3', '', 'eval').co_positions())
    '''

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

def _create_typing_tuple(argz, *args): #NOTE: workaround python/cpython#94245
    if not argz:
        return typing.Tuple[()].copy_with(())
    if argz == ((),):
        return typing.Tuple[()]
    return typing.Tuple[argz]

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
            pickler.write(POP)

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

def _module_map(main_module):
    """get map of imported modules"""
    from collections import defaultdict
    from types import SimpleNamespace
    modmap = SimpleNamespace(
        by_name = defaultdict(list),
        by_id = defaultdict(list),
        top_level = {},  # top-level modules
        module = main_module.__name__,
        package = _module_package(main_module),
    )
    for modname, module in sys.modules.items():
        if (modname in ('__main__', '__mp_main__') or module is main_module
                or not isinstance(module, ModuleType)):
            continue
        if '.' not in modname:
            modmap.top_level[id(module)] = modname
        for objname, modobj in module.__dict__.items():
            modmap.by_name[objname].append((modobj, modname))
            modmap.by_id[id(modobj)].append((objname, modname))
    return modmap

def _lookup_module(modmap, name, obj, lookup_by_id=True) -> typing.Tuple[str, str, bool]:
    """Lookup name or id of obj if module is imported.

    Lookup for objects identical to 'obj' at modules in 'modmpap'.  If multiple
    copies are found in different modules, return the one from the module with
    higher probability of being available at unpickling time, according to the
    hierarchy:

    1. Standard Library modules
    2. modules of the same top-level package as the module being saved (if it's part of a package)
    3. installed modules in general
    4. non-installed modules

    Returns:
        A 3-tuple containing the module's name, the object's name in the module,
        and a boolean flag, which is `True` if the module falls under categories
        (1) to (3) from the hierarchy, or `False` if it's in category (4).
    """
    not_found = None, None, None
    # Don't look for objects likely related to the module itself.
    obj_module = getattr(obj, '__module__', type(obj).__module__)
    if obj_module == modmap.module:
        return not_found
    obj_package = _module_package(_import_module(obj_module, safe=True))

    for map, by_id in [(modmap.by_name, False), (modmap.by_id, True)]:
        if by_id and not lookup_by_id:
            break
        _2nd_choice = _3rd_choice = _4th_choice = None
        key = id(obj) if by_id else name
        for other, modname in map[key]:
            if by_id or other is obj:
                other_name = other if by_id else name
                other_module = sys.modules[modname]
                other_package = _module_package(other_module)
                # Don't return a reference to a module of another package
                # if the object is likely from the same top-level package.
                if (modmap.package and obj_package == modmap.package
                        and other_package != modmap.package):
                    continue
                # Prefer modules imported earlier (the first found).
                if _is_stdlib_module(other_module):
                    return modname, other_name, True
                elif modmap.package and modmap.package == other_package:
                    if _2nd_choice: continue
                    _2nd_choice = modname, other_name, True
                elif not _2nd_choice:
                    # Don't call _is_builtin_module() unnecessarily.
                    if _is_builtin_module(other_module):
                        if _3rd_choice: continue
                        _3rd_choice = modname, other_name, True
                    else:
                        if _4th_choice: continue
                        _4th_choice = modname, other_name, False  # unsafe
        found = _2nd_choice or _3rd_choice or _4th_choice
        if found:
            return found
    return not_found

def _global_string(modname, name):
    return GLOBAL + bytes('%s\n%s\n' % (modname, name), 'UTF-8')

def _save_module_dict(pickler, main_dict):
    """Save a module's dictionary, saving unpickleable variables by referece."""
    main = getattr(pickler, '_original_main', pickler._main)
    modmap = getattr(pickler, '_modmap', None)  # cached from _stash_modules()
    is_builtin = _is_builtin_module(main)
    pickler.write(MARK + DICT)  # don't need to memoize
    for name, value in main_dict.items():
        pickler.save(name)
        try:
            if pickler.save(value):
                global_name = getattr(value, '__qualname__', value.__name__)
                pickler._saved_byref.append((name, value.__module__, global_name))
        except UNPICKLEABLE_ERRORS as error_stack:
            if modmap is None:
                modmap = _module_map(main)
            modname, objname, installed = _lookup_module(modmap, name, value)
            if modname and (installed or not is_builtin):
                pickler.write(_global_string(modname, objname))
                pickler._saved_byref.append((name, modname, objname))
            elif is_builtin:
                pickler.write(_global_string(main.__name__, name))
                pickler._saved_byref.append((name, main.__name__, name))
            else:
                error = PicklingError("can't save variable %r as global" % name)
                error.name = name
                raise error from error_stack
            pickler.memoize(value)
        pickler.write(SETITEM)

def _repr_dict(obj):
    """Make a short string representation of a dictionary."""
    return "<%s object at %#012x>" % (type(obj).__name__, id(obj))

@register(dict)
def save_module_dict(pickler, obj):
    is_pickler_dill = is_dill(pickler, child=False)
    if (is_pickler_dill
            and obj is pickler._main.__dict__
            and not (pickler._session and pickler._first_pass)):
        logger.trace(pickler, "D1: %s", _repr_dict(obj), obj=obj)
        pickler.write(GLOBAL + b'__builtin__\n__main__\n')
        logger.trace(pickler, "# D1")
    elif not is_pickler_dill and obj is _main_module.__dict__: #prama: no cover
        logger.trace(pickler, "D3: %s", _repr_dict(obj), obj=obj)
        pickler.write(GLOBAL + b'__main__\n__dict__\n')  #XXX: works in general?
        logger.trace(pickler, "# D3")
    elif (is_pickler_dill
            and pickler._session
            and pickler._refonfail
            and obj is pickler._main_dict_copy):
        logger.trace(pickler, "D5: %s", _repr_dict(obj), obj=obj)
        # we only care about session the first pass thru
        pickler.first_pass = False
        _save_module_dict(pickler, obj)
        logger.trace(pickler, "# D5")
    elif ('__name__' in obj
            and obj is not _main_module.__dict__
            and type(obj['__name__']) is str
            and obj is getattr(_import_module(obj['__name__'], safe=True), '__dict__', None)):
        logger.trace(pickler, "D4: %s", _repr_dict(obj), obj=obj)
        pickler.write(_global_string(obj['__name__'], '__dict__'))
        logger.trace(pickler, "# D4")
    else:
        logger.trace(pickler, "D2: %s", _repr_dict(obj), obj=obj)
        if is_pickler_dill:
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

@register(typing._GenericAlias)
def save_generic_alias(pickler, obj):
    args = obj.__args__
    if type(obj.__reduce__()) is str:
        logger.trace(pickler, "Ga0: %s", obj)
        StockPickler.save_global(pickler, obj, name=obj.__reduce__())
        logger.trace(pickler, "# Ga0")
    elif obj.__origin__ is tuple and (not args or args == ((),)):
        logger.trace(pickler, "Ga1: %s", obj)
        pickler.save_reduce(_create_typing_tuple, (args,), obj=obj)
        logger.trace(pickler, "# Ga1")
    else:
        logger.trace(pickler, "Ga2: %s", obj)
        StockPickler.save_reduce(pickler, *obj.__reduce__(), obj=obj)
        logger.trace(pickler, "# Ga2")
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
        pickler.write(POP)
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
        logger.trace(pickler, "Mp: %s", _repr_dict(obj), obj=obj)
        mapping = obj | _dictproxy_helper_instance
        pickler.save_reduce(DictProxyType, (mapping,), obj=obj)
        logger.trace(pickler, "# Mp")
        return
else:
    @register(DictProxyType)
    def save_dictproxy(pickler, obj):
        logger.trace(pickler, "Mp: %s", _repr_dict(obj), obj=obj)
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
    # Must do string substitution here and use %r to avoid ReferenceError.
    logger.trace(pickler, "R2: %r" % obj, obj=obj)
    refobj = _locate_object(_proxy_helper(obj))
    pickler.save_reduce(_create_weakproxy, (refobj, callable(obj)), obj=obj)
    logger.trace(pickler, "# R2")
    return

def _weak_cache(func=None, *, defaults=None):
    if defaults is None:
        defaults = {}
    if func is None:
        return partial(_weak_cache, defaults=defaults)
    cache = weakref.WeakKeyDictionary()
    @wraps(func)
    def wrapper(referent):
        try:
            return defaults[referent]
        except KeyError:
            try:
                return cache[referent]
            except KeyError:
                value = func(referent)
                cache[referent] = value
                return value
    return wrapper

@_weak_cache(defaults={None: False})
def _is_imported_module(module):
    return getattr(module, '__loader__', None) is not None or module in sys.modules.values()

PYTHONPATH_PREFIXES = {getattr(sys, attr) for attr in (
        'base_prefix', 'prefix', 'base_exec_prefix', 'exec_prefix',
        'real_prefix',  # for old virtualenv versions
        ) if hasattr(sys, attr)}
PYTHONPATH_PREFIXES = tuple(os.path.realpath(path) for path in PYTHONPATH_PREFIXES)
EXTENSION_SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)
if OLD310:
    STDLIB_PREFIX = os.path.dirname(os.path.realpath(os.__file__))

@_weak_cache(defaults={None: True})  #XXX: shouldn't return False for None?
def _is_builtin_module(module):
    if module.__name__ in ('__main__', '__mp_main__'):
        return False
    mod_path = getattr(module, '__file__', None)
    if not mod_path:
        return _is_imported_module(module)
    # If a module file name starts with prefix, it should be a builtin
    # module, so should always be pickled as a reference.
    mod_path = os.path.realpath(mod_path)
    return (
        any(mod_path.startswith(prefix) for prefix in PYTHONPATH_PREFIXES)
        or mod_path.endswith(EXTENSION_SUFFIXES)
        or 'site-packages' in mod_path
    )

@_weak_cache(defaults={None: False})
def _is_stdlib_module(module):
    first_level = module.__name__.partition('.')[0]
    if OLD310:
        if first_level in sys.builtin_module_names:
            return True
        mod_path = getattr(module, '__file__', '')
        if mod_path:
            mod_path = os.path.realpath(mod_path)
        return mod_path.startswith(STDLIB_PREFIX)
    else:
        return first_level in sys.stdlib_module_names

@_weak_cache(defaults={None: None})
def _module_package(module):
    """get the top-level package of a module, if any"""
    package = getattr(module, '__package__', None)
    return package.partition('.')[0] if package else None

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
                logger.info("Diff: %s", changed.keys())
                pickler.save_reduce(_import_module, (obj.__name__,), obj=obj,
                                    state=changed)
                logger.trace(pickler, "# M2")
                return

        logger.trace(pickler, "M1: %s", obj)
        pickler.save_reduce(_import_module, (obj.__name__,), obj=obj)
        logger.trace(pickler, "# M1")
    else:
        builtin_mod = _is_builtin_module(obj)
        is_session_main = is_dill(pickler, child=True) and obj is pickler._main
        if (obj.__name__ not in ("builtins", "dill", "dill._dill") and not builtin_mod
                or is_session_main):
            logger.trace(pickler, "M1: %s", obj)
            # Hack for handling module-type objects in load_module().
            mod_name = obj.__name__ if _is_imported_module(obj) else '__runtime__.%s' % obj.__name__
            # Second references are saved as __builtin__.__main__ in save_module_dict().
            main_dict = obj.__dict__.copy()
            for item in ('__builtins__', '__loader__'):
                main_dict.pop(item, None)
            for item in IPYTHON_SINGLETONS: #pragma: no cover
                if getattr(main_dict.get(item), '__module__', '').startswith('IPython'):
                    del main_dict[item]
            if is_session_main:
                pickler._main_dict_copy = main_dict
            pickler.save_reduce(_import_module, (mod_name,), obj=obj, state=main_dict)
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
        pickler.write(GLOBAL + b'__builtin__\nNoneType\n')
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
            # thanks to Tom Stepleton pointing out pickler._session unneeded
            logger.trace(pickler, "T2: %s", obj)
            _dict = obj.__dict__.copy() # convert dictproxy to dict
           #print (_dict)
           #print ("%s\n%s" % (type(obj), obj.__name__))
           #print ("%s\n%s" % (obj.__bases__, obj.__dict__))
            slots = _dict.get('__slots__', ())
            if type(slots) == str: slots = (slots,) # __slots__ accepts a single string
            for name in slots:
                del _dict[name]
            _dict.pop('__dict__', None)
            _dict.pop('__weakref__', None)
            _dict.pop('__prepare__', None)
            if obj_name != obj.__name__:
                if postproc_list is None:
                    postproc_list = []
                postproc_list.append((setattr, (obj, '__qualname__', obj_name)))
            _save_with_postproc(pickler, (_create_type, (
                type(obj), obj.__name__, obj.__bases__, _dict
            )), obj=obj, postproc_list=postproc_list)
            logger.trace(pickler, "# T2")
        else:
            logger.trace(pickler, "T4: %s", obj)
            if incorrectly_named:
                warnings.warn(
                    "Cannot locate reference to %r." % (obj,),
                    PicklingWarning,
                    stacklevel=3,
                )
            if obj_recursive:
                warnings.warn(
                    "Cannot pickle %r: %s.%s has recursive self-references that "
                    "trigger a RecursionError." % (obj, obj.__module__, obj_name),
                    PicklingWarning,
                    stacklevel=3,
                )
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
        _original_main = getattr(pickler, '_original_main', None)
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
            if _original_main is not None and globs_copy is _original_main.__dict__:
                globs_copy = pickler._main.__dict__
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
                    pickler.write(POP)

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


#############################
# A quick fix for issue #500
# This should be removed when a better solution is found.

if hasattr(dataclasses, "_HAS_DEFAULT_FACTORY_CLASS"):
    @register(dataclasses._HAS_DEFAULT_FACTORY_CLASS)
    def save_dataclasses_HAS_DEFAULT_FACTORY_CLASS(pickler, obj):
        logger.trace(pickler, "DcHDF: %s", obj)
        pickler.write(GLOBAL + b"dataclasses\n_HAS_DEFAULT_FACTORY\n")
        logger.trace(pickler, "# DcHDF")

if hasattr(dataclasses, "MISSING"):
    @register(type(dataclasses.MISSING))
    def save_dataclasses_MISSING_TYPE(pickler, obj):
        logger.trace(pickler, "DcM: %s", obj)
        pickler.write(GLOBAL + b"dataclasses\nMISSING\n")
        logger.trace(pickler, "# DcM")

if hasattr(dataclasses, "KW_ONLY"):
    @register(type(dataclasses.KW_ONLY))
    def save_dataclasses_KW_ONLY_TYPE(pickler, obj):
        logger.trace(pickler, "DcKWO: %s", obj)
        pickler.write(GLOBAL + b"dataclasses\nKW_ONLY\n")
        logger.trace(pickler, "# DcKWO")

if hasattr(dataclasses, "_FIELD_BASE"):
    @register(dataclasses._FIELD_BASE)
    def save_dataclasses_FIELD_BASE(pickler, obj):
        logger.trace(pickler, "DcFB: %s", obj)
        pickler.write(GLOBAL + b"dataclasses\n" + obj.name.encode() + b"\n")
        logger.trace(pickler, "# DcFB")

#############################

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
        exceptions = UNPICKLEABLE_ERRORS + (AssertionError, UnpicklingError)
    try:
        pik = copy(obj, **kwds)
        #FIXME: should check types match first, then check content if "exact"
        try:
            #FIXME: should be "(pik == obj).all()" for numpy comparison, though that'll fail if shapes differ
            result = bool(pik.all() == obj.all())
        except (AttributeError, TypeError):
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
