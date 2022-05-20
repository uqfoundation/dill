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
__all__ = ['dump','dumps','load','loads','dump_session','load_session',
           'Pickler','Unpickler','register','copy','pickle','pickles',
           'check','HIGHEST_PROTOCOL','DEFAULT_PROTOCOL','PicklingError',
           'UnpicklingError','HANDLE_FMODE','CONTENTS_FMODE','FILE_FMODE',
           'PickleError','PickleWarning','PicklingWarning','UnpicklingWarning']

import logging
log = logging.getLogger("dill")
log.addHandler(logging.StreamHandler())
def _trace(boolean):
    """print a trace through the stack when pickling; useful for debugging"""
    if boolean: log.setLevel(logging.INFO)
    else: log.setLevel(logging.WARN)
    return
import warnings

import os
import sys
diff = None
_use_diff = False
PY3 = (sys.hexversion >= 0x3000000)
# OLDER: 3.0 <= x < 3.4 *OR* x < 2.7.10  #NOTE: guessing relevant versions
OLDER = (PY3 and sys.hexversion < 0x3040000) or (sys.hexversion < 0x2070ab1)
OLD33 = (sys.hexversion < 0x3030000)
OLD37 = (sys.hexversion < 0x3070000)
OLD39 = (sys.hexversion < 0x3090000)
OLD310 = (sys.hexversion < 0x30a0000)
PY34 = (0x3040000 <= sys.hexversion < 0x3050000)
if PY3: #XXX: get types from .objtypes ?
    import builtins as __builtin__
    from pickle import _Pickler as StockPickler, Unpickler as StockUnpickler
    from _thread import LockType
    if (sys.hexversion >= 0x30200f0):
        from _thread import RLock as RLockType
    else:
        from threading import _RLock as RLockType
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
    if OLD33:
        DictProxyType = type(object.__dict__)
    else:
        from types import MappingProxyType as DictProxyType
else:
    import __builtin__
    from pickle import Pickler as StockPickler, Unpickler as StockUnpickler
    from thread import LockType
    from threading import _RLock as RLockType
    from types import CodeType, FunctionType, ClassType, MethodType, \
         GeneratorType, DictProxyType, XRangeType, SliceType, TracebackType, \
         NotImplementedType, EllipsisType, FrameType, ModuleType, \
         BufferType, BuiltinMethodType, TypeType
from pickle import HIGHEST_PROTOCOL, PickleError, PicklingError, UnpicklingError
try:
    from pickle import DEFAULT_PROTOCOL
except ImportError:
    DEFAULT_PROTOCOL = HIGHEST_PROTOCOL
import __main__ as _main_module
import marshal
import gc
# import zlib
from weakref import ReferenceType, ProxyType, CallableProxyType
from functools import partial
from operator import itemgetter, attrgetter
# new in python3.3
if sys.hexversion < 0x03030000:
    FileNotFoundError = IOError
if PY3 and sys.hexversion < 0x03040000:
    GENERATOR_FAIL = True
else: GENERATOR_FAIL = False
if PY3:
    import importlib.machinery
    EXTENSION_SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)
else:
    import imp
    EXTENSION_SUFFIXES = tuple(suffix
                               for (suffix, _, s_type) in imp.get_suffixes()
                               if s_type == imp.C_EXTENSION)
try:
    import ctypes
    HAS_CTYPES = True
    # if using `pypy`, pythonapi is not found
    IS_PYPY = not hasattr(ctypes, 'pythonapi')
except ImportError:
    HAS_CTYPES = False
    IS_PYPY = False
IS_PYPY2 = IS_PYPY and not PY3
NumpyUfuncType = None
NumpyDType = None
NumpyArrayType = None
try:
    if OLDER:
        raise AttributeError('find_spec not found')
    import importlib
    if not importlib.machinery.PathFinder().find_spec('numpy'):
        raise ImportError("No module named 'numpy'")
    NumpyUfuncType = True
    NumpyDType = True
    NumpyArrayType = True
except AttributeError:
    try:
        import imp
        imp.find_module('numpy')
        NumpyUfuncType = True
        NumpyDType = True
        NumpyArrayType = True
    except ImportError:
        pass
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

# make sure to add these 'hand-built' types to _typemap
if PY3:
    CellType = type((lambda x: lambda y: x)(0).__closure__[0])
else:
    CellType = type((lambda x: lambda y: x)(0).func_closure[0])
# new in python2.5
if sys.hexversion >= 0x20500f0:
    from types import GetSetDescriptorType
    if not IS_PYPY:
        from types import MemberDescriptorType
    else:
        # oddly, MemberDescriptorType is GetSetDescriptorType
        # while, member_descriptor does exist otherwise... is this a pypy bug?
        class _member(object):
            __slots__ = ['descriptor']
        MemberDescriptorType = type(_member.descriptor)
if IS_PYPY:
    WrapperDescriptorType = MethodType
    MethodDescriptorType = FunctionType
    ClassMethodDescriptorType = FunctionType
else:
    WrapperDescriptorType = type(type.__repr__)
    MethodDescriptorType = type(type.__dict__['mro'])
    ClassMethodDescriptorType = type(type.__dict__['__prepare__' if PY3 else 'mro'])

MethodWrapperType = type([].__repr__)
PartialType = type(partial(int,base=2))
SuperType = type(super(Exception, TypeError()))
ItemGetterType = type(itemgetter(0))
AttrGetterType = type(attrgetter('__repr__'))

try:
    from functools import _lru_cache_wrapper as LRUCacheType
except:
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
try:
    from cStringIO import StringIO, InputType, OutputType
except ImportError:
    if PY3:
        from io import BytesIO as StringIO
    else:
        from StringIO import StringIO
    InputType = OutputType = None
if not IS_PYPY2:
    from socket import socket as SocketType
    try: #FIXME: additionally calls ForkingPickler.register several times
        from multiprocessing.reduction import _reduce_socket as reduce_socket
    except ImportError:
        from multiprocessing.reduction import reduce_socket
try:
    __IPYTHON__ is True # is ipython
    ExitType = None     # IPython.core.autocall.ExitAutocall
    singletontypes = ['exit', 'quit', 'get_ipython']
except NameError:
    try: ExitType = type(exit) # apparently 'exit' can be removed
    except NameError: ExitType = None
    singletontypes = []

from collections import OrderedDict

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
SESSION_IMPORTED_AS_TYPES = (ModuleType, ClassType, TypeType, Exception,
                             FunctionType, MethodType, BuiltinMethodType)

def _module_map():
    """get map of imported modules"""
    from collections import defaultdict, namedtuple
    modmap = namedtuple('Modmap', ['by_name', 'by_id', 'top_level'])
    modmap = modmap(defaultdict(list), defaultdict(list), {})
    items = 'items' if PY3 else 'iteritems'
    for modname, module in getattr(sys.modules, items)():
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
    items = 'items' if PY3 else 'iteritems'
    for name, obj in getattr(main_module.__dict__, items)():
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
def dump_session(filename='/tmp/session.pkl', main=None, byref=False, **kwds):
    """pickle the current state of __main__ to a file"""
    from .settings import settings
    protocol = settings['protocol']
    if main is None: main = _main_module
    if hasattr(filename, 'write'):
        f = filename
    else:
        f = open(filename, 'wb')
    try:
        pickler = Pickler(f, protocol, **kwds)
        pickler._original_main = main
        if byref:
            main = _stash_modules(main)
        pickler._main = main     #FIXME: dill.settings are disabled
        pickler._byref = False   # disable pickling by name reference
        pickler._recurse = False # disable pickling recursion for globals
        pickler._session = True  # is best indicator of when pickling a session
        pickler._first_pass = True
        pickler._main_modified = main is not pickler._original_main
        pickler.dump(main)
    finally:
        if f is not filename:  # If newly opened file
            f.close()
    return

def load_session(filename='/tmp/session.pkl', main=None, **kwds):
    """update the __main__ module with the state from the session file"""
    if main is None: main = _main_module
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

    def __init__(self, *args, **kwds):
        settings = Pickler.settings
        _byref = kwds.pop('byref', None)
       #_strictio = kwds.pop('strictio', None)
        _fmode = kwds.pop('fmode', None)
        _recurse = kwds.pop('recurse', None)
        StockPickler.__init__(self, *args, **kwds)
        self._main = _main_module
        self._diff_cache = {}
        self._byref = settings['byref'] if _byref is None else _byref
        self._strictio = False #_strictio
        self._fmode = settings['fmode'] if _fmode is None else _fmode
        self._recurse = settings['recurse'] if _recurse is None else _recurse
        from collections import OrderedDict
        self._postproc = OrderedDict()

    def dump(self, obj): #NOTE: if settings change, need to update attributes
        # register if the object is a numpy ufunc
        # thanks to Paul Kienzle for pointing out ufuncs didn't pickle
        if NumpyUfuncType and numpyufunc(obj):
            @register(type(obj))
            def save_numpy_ufunc(pickler, obj):
                log.info("Nu: %s" % obj)
                name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
                StockPickler.save_global(pickler, obj, name=name)
                log.info("# Nu")
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
                log.info("Dt: %s" % obj)
                pickler.save_reduce(_create_dtypemeta, (obj.type,), obj=obj)
                log.info("# Dt")
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
                log.info("Nu: (%s, %s)" % (obj.shape,obj.dtype))
                npdict = getattr(obj, '__dict__', None)
                f, args, state = obj.__reduce__()
                pickler.save_reduce(_create_array, (f,args,state,npdict), obj=obj)
                log.info("# Nu")
                return
        # end hack
        if GENERATOR_FAIL and type(obj) == GeneratorType:
            msg = "Can't pickle %s: attribute lookup builtins.generator failed" % GeneratorType
            raise PicklingError(msg)
        else:
            StockPickler.dump(self, obj)
        return
    dump.__doc__ = StockPickler.dump.__doc__
    pass

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
        except:
            import diff as d
        diff = d

def _create_typemap():
    import types
    if PY3:
        d = dict(list(__builtin__.__dict__.items()) + \
                 list(types.__dict__.items())).items()
        builtin = 'builtins'
    else:
        d = types.__dict__.iteritems()
        builtin = '__builtin__'
    for key, value in d:
        if getattr(value, '__module__', None) == builtin \
        and type(value) is type:
            yield key, value
    return
_reverse_typemap = dict(_create_typemap())
_reverse_typemap.update({
    'CellType': CellType,
    'MethodWrapperType': MethodWrapperType,
    'PartialType': PartialType,
    'SuperType': SuperType,
    'ItemGetterType': ItemGetterType,
    'AttrGetterType': AttrGetterType,
    'FileType': FileType,
    'BufferedRandomType': BufferedRandomType,
    'BufferedReaderType': BufferedReaderType,
    'BufferedWriterType': BufferedWriterType,
    'TextWrapperType': TextWrapperType,
    'PyBufferedRandomType': PyBufferedRandomType,
    'PyBufferedReaderType': PyBufferedReaderType,
    'PyBufferedWriterType': PyBufferedWriterType,
    'PyTextWrapperType': PyTextWrapperType,
})
if ExitType:
    _reverse_typemap['ExitType'] = ExitType
if InputType:
    _reverse_typemap['InputType'] = InputType
    _reverse_typemap['OutputType'] = OutputType
if not IS_PYPY:
    _reverse_typemap['WrapperDescriptorType'] = WrapperDescriptorType
    _reverse_typemap['MethodDescriptorType'] = MethodDescriptorType
    _reverse_typemap['ClassMethodDescriptorType'] = ClassMethodDescriptorType
else:
    _reverse_typemap['MemberDescriptorType'] = MemberDescriptorType
if PY3:
    _typemap = dict((v, k) for k, v in _reverse_typemap.items())
else:
    _typemap = dict((v, k) for k, v in _reverse_typemap.iteritems())

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

def _create_code(*args):
    if PY3 and hasattr(args[-3], 'encode'): #FIXME: from PY2 fails (optcode)
        args = list(args)
        if len(args) == 20:
            args[-3] = args[-3].encode() # co_exceptiontable
            args[-6] = args[-6].encode() # co_lnotab
            args[-14] = args[-14].encode() # co_code
            if args[-4] is not None:
                args[-4] = args[-4].encode() # co_columntable
            if args[-5] is not None:
                args[-5] = args[-5].encode() # co_endlinetable
        else:
            args[-3] = args[-3].encode() # co_lnotab
            args[-10] = args[-10].encode() # co_code
    if hasattr(CodeType, 'co_exceptiontable'):
        if len(args) == 20: return CodeType(*args)
        elif len(args) == 16:
            argz = (None, None, b'')
            argz = args[:-4] + args[-5:-4] + args[-4:-2] + argz + args[-2:]
            return CodeType(*argz)
        elif len(args) == 15:
            argz = args[1:-4] + args[-5:-4] + args[-4:-2] + argz + args[-2:]
            return CodeType(args[0], 0, *argz)
        argz = args[1:-4] + args[-5:-4] + args[-4:-2] + argz + args[-2:]
        return CodeType(args[0], 0, 0, *argz)
    elif hasattr(CodeType, 'co_posonlyargcount'):
        if len(args) == 20:
            return CodeType(*(args[:12] + args[13:15] + args[18:]))
        elif len(args) == 16: return CodeType(*args)
        elif len(args) == 15: return CodeType(args[0], 0, *args[1:])
        return CodeType(args[0], 0, 0, *args[1:])
    elif hasattr(CodeType, 'co_kwonlyargcount'):
        if len(args) == 20:
            return CodeType(*(args[:1] + args[2:12] + args[13:15] + args[18:]))
        elif len(args) == 16: return CodeType(args[0], *args[2:])
        elif len(args) == 15: return CodeType(*args)
        return CodeType(args[0], 0, *args[1:])
    if len(args) == 20:
        return CodeType(*(args[:1] + args[3:12] + args[13:15] + args[18:]))
    elif len(args) == 16: return CodeType(args[0], *args[3:])
    elif len(args) == 15: return CodeType(args[0], *args[2:])
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
        # treat x mode as w mode
        if "x" in mode and sys.hexversion < 0x03030000:
            raise ValueError("invalid mode: '%s'" % mode)
        try:
            exists = os.path.exists(name)
        except:
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
                if PY3:
                    r = getattr(f, "buffer", f)
                    r = getattr(r, "raw", r)
                    r.name = name
                else:
                    if not HAS_CTYPES:
                        raise ImportError("No module named 'ctypes'")
                    class FILE(ctypes.Structure):
                        _fields_ = [("refcount", ctypes.c_long),
                                    ("type_obj", ctypes.py_object),
                                    ("file_pointer", ctypes.c_voidp),
                                    ("name", ctypes.py_object)]

                    class PyObject(ctypes.Structure):
                        _fields_ = [
                            ("ob_refcnt", ctypes.c_int),
                            ("ob_type", ctypes.py_object)
                            ]
                    #FIXME: CONTENTS_FMODE fails for pypy due to issue #1233
                    #       https://bitbucket.org/pypy/pypy/issues/1233
                    ctypes.cast(id(f), ctypes.POINTER(FILE)).contents.name = name
                    ctypes.cast(id(name), ctypes.POINTER(PyObject)).contents.ob_refcnt += 1
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
except:
    MAPPING_PROXY_TRICK = False
del __d

# _CELL_REF and _CELL_EMPTY are used to stay compatible with versions of dill
# whose _create_cell functions do not have a default value.
# _CELL_REF can be safely removed entirely (replaced by empty tuples for calls
# to _create_cell) once breaking changes are allowed.
_CELL_REF = None
_CELL_EMPTY = Sentinel('_CELL_EMPTY')

if PY3:
    def _create_cell(contents=None):
        if contents is not _CELL_EMPTY:
            value = contents
        return (lambda: value).__closure__[0]

else:
    def _create_cell(contents=None):
        if contents is not _CELL_EMPTY:
            value = contents
        return (lambda: value).func_closure[0]


def _create_weakref(obj, *args):
    from weakref import ref
    if obj is None: # it's dead
        if PY3:
            from collections import UserDict
        else:
            from UserDict import UserDict
        return ref(UserDict(), *args)
    return ref(obj, *args)

def _create_weakproxy(obj, callable=False, *args):
    from weakref import proxy
    if obj is None: # it's dead
        if callable: return proxy(lambda x:x, *args)
        if PY3:
            from collections import UserDict
        else:
            from UserDict import UserDict
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

if OLD37:
    def _create_namedtuple(name, fieldnames, modulename, defaults=None):
        class_ = _import_module(modulename + '.' + name, safe=True)
        if class_ is not None:
            return class_
        import collections
        t = collections.namedtuple(name, fieldnames)
        t.__module__ = modulename
        return t
else:
    def _create_namedtuple(name, fieldnames, modulename, defaults=None):
        class_ = _import_module(modulename + '.' + name, safe=True)
        if class_ is not None:
            return class_
        import collections
        t = collections.namedtuple(name, fieldnames, defaults=defaults, module=modulename)
        return t

def _getattr(objclass, name, repr_str):
    # hack to grab the reference directly
    try: #XXX: works only for __builtin__ ?
        attr = repr_str.split("'")[3]
        return eval(attr+'.__dict__["'+name+'"]')
    except:
        try:
            attr = objclass.__dict__
            if type(attr) is DictProxyType:
                attr = attr[name]
            else:
                attr = getattr(objclass,name)
        except:
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
        if '.' in import_name:
            items = import_name.split('.')
            module = '.'.join(items[:-1])
            obj = items[-1]
        else:
            return __import__(import_name)
        return getattr(__import__(module, None, None, [obj]), obj)
    except (ImportError, AttributeError):
        if safe:
            return None
        raise

def _locate_function(obj, pickler=None):
    if obj.__module__ in ['__main__', None] or \
            pickler and is_dill(pickler, child=False) and pickler._session and obj.__module__ == pickler._main.__name__:
        return False

    found = _import_module(obj.__module__ + '.' + obj.__name__, safe=True)
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
            if PY3:
                pickler.write(bytes('0', 'UTF-8'))
            else:
                pickler.write('0')

#@register(CodeType)
#def save_code(pickler, obj):
#    log.info("Co: %s" % obj)
#    pickler.save_reduce(_unmarshal, (marshal.dumps(obj),), obj=obj)
#    log.info("# Co")
#    return

# The following function is based on 'save_codeobject' from 'cloudpickle'
# Copyright (c) 2012, Regents of the University of California.
# Copyright (c) 2009 `PiCloud, Inc. <http://www.picloud.com>`_.
# License: https://github.com/cloudpipe/cloudpickle/blob/master/LICENSE
@register(CodeType)
def save_code(pickler, obj):
    log.info("Co: %s" % obj)
    if PY3:
        if hasattr(obj, "co_exceptiontable"):
            args = (
                obj.co_argcount, obj.co_posonlyargcount,
                obj.co_kwonlyargcount, obj.co_nlocals, obj.co_stacksize,
                obj.co_flags, obj.co_code, obj.co_consts, obj.co_names,
                obj.co_varnames, obj.co_filename, obj.co_name, obj.co_qualname,
                obj.co_firstlineno, obj.co_lnotab, obj.co_endlinetable,
                obj.co_columntable, obj.co_exceptiontable, obj.co_freevars,
                obj.co_cellvars
        )
        elif hasattr(obj, "co_posonlyargcount"):
            args = (
                obj.co_argcount, obj.co_posonlyargcount,
                obj.co_kwonlyargcount, obj.co_nlocals, obj.co_stacksize,
                obj.co_flags, obj.co_code, obj.co_consts, obj.co_names,
                obj.co_varnames, obj.co_filename, obj.co_name,
                obj.co_firstlineno, obj.co_lnotab, obj.co_freevars,
                obj.co_cellvars
        )
        else:
            args = (
                obj.co_argcount, obj.co_kwonlyargcount, obj.co_nlocals,
                obj.co_stacksize, obj.co_flags, obj.co_code, obj.co_consts,
                obj.co_names, obj.co_varnames, obj.co_filename,
                obj.co_name, obj.co_firstlineno, obj.co_lnotab,
                obj.co_freevars, obj.co_cellvars
        )
    else:
        args = (
            obj.co_argcount, obj.co_nlocals, obj.co_stacksize, obj.co_flags,
            obj.co_code, obj.co_consts, obj.co_names, obj.co_varnames,
            obj.co_filename, obj.co_name, obj.co_firstlineno, obj.co_lnotab,
            obj.co_freevars, obj.co_cellvars
        )

    pickler.save_reduce(_create_code, args, obj=obj)
    log.info("# Co")
    return

@register(dict)
def save_module_dict(pickler, obj):
    if is_dill(pickler, child=False) and obj == pickler._main.__dict__ and \
            not (pickler._session and pickler._first_pass):
        log.info("D1: <dict%s" % str(obj.__repr__).split('dict')[-1]) # obj
        if PY3:
            pickler.write(bytes('c__builtin__\n__main__\n', 'UTF-8'))
        else:
            pickler.write('c__builtin__\n__main__\n')
        log.info("# D1")
    elif (not is_dill(pickler, child=False)) and (obj == _main_module.__dict__):
        log.info("D3: <dict%s" % str(obj.__repr__).split('dict')[-1]) # obj
        if PY3:
            pickler.write(bytes('c__main__\n__dict__\n', 'UTF-8'))
        else:
            pickler.write('c__main__\n__dict__\n')   #XXX: works in general?
        log.info("# D3")
    elif '__name__' in obj and obj != _main_module.__dict__ \
    and type(obj['__name__']) is str \
    and obj is getattr(_import_module(obj['__name__'],True), '__dict__', None):
        log.info("D4: <dict%s" % str(obj.__repr__).split('dict')[-1]) # obj
        if PY3:
            pickler.write(bytes('c%s\n__dict__\n' % obj['__name__'], 'UTF-8'))
        else:
            pickler.write('c%s\n__dict__\n' % obj['__name__'])
        log.info("# D4")
    else:
        log.info("D2: <dict%s" % str(obj.__repr__).split('dict')[-1]) # obj
        if is_dill(pickler, child=False) and pickler._session:
            # we only care about session the first pass thru
            pickler._first_pass = False
        StockPickler.save_dict(pickler, obj)
        log.info("# D2")
    return


if not OLD310 and MAPPING_PROXY_TRICK:
    def save_dict_view(dicttype):
        def save_dict_view_for_function(func):
            def _save_dict_view(pickler, obj):
                log.info("Dkvi: <%s>" % (obj,))
                mapping = obj.mapping | _dictproxy_helper_instance
                pickler.save_reduce(func, (mapping,), obj=obj)
                log.info("# Dkvi")
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
            log.info("Dk: <%s>" % (obj,))
            dict_constructor = _shims.Reduce(dicttype.fromkeys, (list(obj),))
            pickler.save_reduce(dicttype.keys, (dict_constructor,), obj=obj)
            log.info("# Dk")

        def save_dict_values(pickler, obj):
            log.info("Dv: <%s>" % (obj,))
            dict_constructor = _shims.Reduce(dicttype, (enumerate(obj),))
            pickler.save_reduce(dicttype.values, (dict_constructor,), obj=obj)
            log.info("# Dv")

        def save_dict_items(pickler, obj):
            log.info("Di: <%s>" % (obj,))
            pickler.save_reduce(dicttype.items, (dicttype(obj),), obj=obj)
            log.info("# Di")

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
        log.info("C1: %s" % obj)
        pickler.save_reduce(ClassType, (obj.__name__, obj.__bases__,
                                        obj.__dict__), obj=obj)
                                       #XXX: or obj.__dict__.copy()), obj=obj) ?
        log.info("# C1")
    else:
        log.info("C2: %s" % obj)
        name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
        StockPickler.save_global(pickler, obj, name=name)
        log.info("# C2")
    return

@register(LockType)
def save_lock(pickler, obj):
    log.info("Lo: %s" % obj)
    pickler.save_reduce(_create_lock, (obj.locked(),), obj=obj)
    log.info("# Lo")
    return

@register(RLockType)
def save_rlock(pickler, obj):
    log.info("RL: %s" % obj)
    r = obj.__repr__() # don't use _release_save as it unlocks the lock
    count = int(r.split('count=')[1].split()[0].rstrip('>'))
    owner = int(r.split('owner=')[1].split()[0]) if PY3 else getattr(obj, '_RLock__owner')
    pickler.save_reduce(_create_rlock, (count,owner,), obj=obj)
    log.info("# RL")
    return

if not IS_PYPY2:
    #@register(SocketType) #FIXME: causes multiprocess test_pickling FAIL
    def save_socket(pickler, obj):
        log.info("So: %s" % obj)
        pickler.save_reduce(*reduce_socket(obj))
        log.info("# So")
        return

if sys.hexversion <= 0x3050000:
    @register(ItemGetterType)
    def save_itemgetter(pickler, obj):
        log.info("Ig: %s" % obj)
        helper = _itemgetter_helper()
        obj(helper)
        pickler.save_reduce(type(obj), tuple(helper.items), obj=obj)
        log.info("# Ig")
        return

    @register(AttrGetterType)
    def save_attrgetter(pickler, obj):
        log.info("Ag: %s" % obj)
        attrs = []
        helper = _attrgetter_helper(attrs)
        obj(helper)
        pickler.save_reduce(type(obj), tuple(attrs), obj=obj)
        log.info("# Ag")
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
    log.info("Fi: %s" % obj)
    f = _save_file(pickler, obj, open)
    log.info("# Fi")
    return f

if PyTextWrapperType:
    @register(PyBufferedRandomType)
    @register(PyBufferedReaderType)
    @register(PyBufferedWriterType)
    @register(PyTextWrapperType)
    def save_file(pickler, obj):
        log.info("Fi: %s" % obj)
        f = _save_file(pickler, obj, _open)
        log.info("# Fi")
        return f

# The following two functions are based on 'saveCStringIoInput'
# and 'saveCStringIoOutput' from spickle
# Copyright (c) 2011 by science+computing ag
# License: http://www.apache.org/licenses/LICENSE-2.0
if InputType:
    @register(InputType)
    def save_stringi(pickler, obj):
        log.info("Io: %s" % obj)
        if obj.closed:
            value = ''; position = 0
        else:
            value = obj.getvalue(); position = obj.tell()
        pickler.save_reduce(_create_stringi, (value, position, \
                                              obj.closed), obj=obj)
        log.info("# Io")
        return

    @register(OutputType)
    def save_stringo(pickler, obj):
        log.info("Io: %s" % obj)
        if obj.closed:
            value = ''; position = 0
        else:
            value = obj.getvalue(); position = obj.tell()
        pickler.save_reduce(_create_stringo, (value, position, \
                                              obj.closed), obj=obj)
        log.info("# Io")
        return

if 0x2050000 <= sys.hexversion < 0x3010000:
    @register(PartialType)
    def save_functor(pickler, obj):
        log.info("Fu: %s" % obj)
        pickler.save_reduce(_create_ftype, (type(obj), obj.func, obj.args,
                                            obj.keywords), obj=obj)
        log.info("# Fu")
        return

if LRUCacheType is not None:
    from functools import lru_cache
    @register(LRUCacheType)
    def save_lru_cache(pickler, obj):
        log.info("LRU: %s" % obj)
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
        log.info("# LRU")
        return

@register(SuperType)
def save_super(pickler, obj):
    log.info("Su: %s" % obj)
    pickler.save_reduce(super, (obj.__thisclass__, obj.__self__), obj=obj)
    log.info("# Su")
    return

if OLDER or not PY3:
    @register(BuiltinMethodType)
    def save_builtin_method(pickler, obj):
        if obj.__self__ is not None:
            if obj.__self__ is __builtin__:
                module = 'builtins' if PY3 else '__builtin__'
                _t = "B1"
                log.info("%s: %s" % (_t, obj))
            else:
                module = obj.__self__
                _t = "B3"
                log.info("%s: %s" % (_t, obj))
            if is_dill(pickler, child=True):
                _recurse = pickler._recurse
                pickler._recurse = False
            pickler.save_reduce(_get_attr, (module, obj.__name__), obj=obj)
            if is_dill(pickler, child=True):
                pickler._recurse = _recurse
            log.info("# %s" % _t)
        else:
            log.info("B2: %s" % obj)
            name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
            StockPickler.save_global(pickler, obj, name=name)
            log.info("# B2")
        return

    @register(MethodType) #FIXME: fails for 'hidden' or 'name-mangled' classes
    def save_instancemethod0(pickler, obj):# example: cStringIO.StringI
        log.info("Me: %s" % obj) #XXX: obj.__dict__ handled elsewhere?
        if PY3:
            pickler.save_reduce(MethodType, (obj.__func__, obj.__self__), obj=obj)
        else:
            pickler.save_reduce(MethodType, (obj.im_func, obj.im_self,
                                             obj.im_class), obj=obj)
        log.info("# Me")
        return

if sys.hexversion >= 0x20500f0:
    if not IS_PYPY:
        @register(MemberDescriptorType)
        @register(GetSetDescriptorType)
        @register(MethodDescriptorType)
        @register(WrapperDescriptorType)
        @register(ClassMethodDescriptorType)
        def save_wrapper_descriptor(pickler, obj):
            log.info("Wr: %s" % obj)
            pickler.save_reduce(_getattr, (obj.__objclass__, obj.__name__,
                                           obj.__repr__()), obj=obj)
            log.info("# Wr")
            return
    else:
        @register(MemberDescriptorType)
        @register(GetSetDescriptorType)
        def save_wrapper_descriptor(pickler, obj):
            log.info("Wr: %s" % obj)
            pickler.save_reduce(_getattr, (obj.__objclass__, obj.__name__,
                                           obj.__repr__()), obj=obj)
            log.info("# Wr")
            return

    @register(MethodWrapperType)
    def save_instancemethod(pickler, obj):
        log.info("Mw: %s" % obj)
        if IS_PYPY2 and obj.__self__ is None and obj.im_class:
            # Can be a class method in PYPY2 if __self__ is none
            pickler.save_reduce(getattr, (obj.im_class, obj.__name__), obj=obj)
            return
        pickler.save_reduce(getattr, (obj.__self__, obj.__name__), obj=obj)
        log.info("# Mw")
        return

elif not IS_PYPY:
    @register(MethodDescriptorType)
    @register(WrapperDescriptorType)
    def save_wrapper_descriptor(pickler, obj):
        log.info("Wr: %s" % obj)
        pickler.save_reduce(_getattr, (obj.__objclass__, obj.__name__,
                                       obj.__repr__()), obj=obj)
        log.info("# Wr")
        return

@register(CellType)
def save_cell(pickler, obj):
    try:
        f = obj.cell_contents
    except:
        log.info("Ce3: %s" % obj)
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
        if PY3:
            pickler.write(bytes('0', 'UTF-8'))
        else:
            pickler.write('0')
        log.info("# Ce3")
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
            log.info("Ce2: %s" % obj)
            # _CELL_REF is defined in _shims.py to support older versions of
            # dill. When breaking changes are made to dill, (_CELL_REF,) can
            # be replaced by ()
            pickler.save_reduce(_create_cell, (_CELL_REF,), obj=obj)
            postproc.append((_shims._setattr, (obj, 'cell_contents', f)))
            log.info("# Ce2")
            return
    log.info("Ce1: %s" % obj)
    pickler.save_reduce(_create_cell, (f,), obj=obj)
    log.info("# Ce1")
    return

if MAPPING_PROXY_TRICK:
    @register(DictProxyType)
    def save_dictproxy(pickler, obj):
        log.info("Mp: %s" % obj)
        mapping = obj | _dictproxy_helper_instance
        pickler.save_reduce(DictProxyType, (mapping,), obj=obj)
        log.info("# Mp")
        return
elif not IS_PYPY:
    if not OLD33:
        @register(DictProxyType)
        def save_dictproxy(pickler, obj):
            log.info("Mp: %s" % obj)
            pickler.save_reduce(DictProxyType, (obj.copy(),), obj=obj)
            log.info("# Mp")
            return
    else:
        # The following function is based on 'saveDictProxy' from spickle
        # Copyright (c) 2011 by science+computing ag
        # License: http://www.apache.org/licenses/LICENSE-2.0
        @register(DictProxyType)
        def save_dictproxy(pickler, obj):
            log.info("Dp: %s" % obj)
            attr = obj.get('__dict__')
           #pickler.save_reduce(_create_dictproxy, (attr,'nested'), obj=obj)
            if type(attr) == GetSetDescriptorType and attr.__name__ == "__dict__" \
            and getattr(attr.__objclass__, "__dict__", None) == obj:
                pickler.save_reduce(getattr, (attr.__objclass__,"__dict__"),obj=obj)
                log.info("# Dp")
                return
            # all bad below... so throw ReferenceError or TypeError
            raise ReferenceError("%s does not reference a class __dict__" % obj)

@register(SliceType)
def save_slice(pickler, obj):
    log.info("Sl: %s" % obj)
    pickler.save_reduce(slice, (obj.start, obj.stop, obj.step), obj=obj)
    log.info("# Sl")
    return

@register(XRangeType)
@register(EllipsisType)
@register(NotImplementedType)
def save_singleton(pickler, obj):
    log.info("Si: %s" % obj)
    pickler.save_reduce(_eval_repr, (obj.__repr__(),), obj=obj)
    log.info("# Si")
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
        if PY3:
            objects = iter(module.__dict__.values())
        else:
            objects = module.__dict__.itervalues()
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
    log.info("R1: %s" % obj)
   #refobj = ctypes.pythonapi.PyWeakref_GetObject(obj) # dead returns "None"
    pickler.save_reduce(_create_weakref, (refobj,), obj=obj)
    log.info("# R1")
    return

@register(ProxyType)
@register(CallableProxyType)
def save_weakproxy(pickler, obj):
    refobj = _locate_object(_proxy_helper(obj))
    try:
        _t = "R2"
        log.info("%s: %s" % (_t, obj))
    except ReferenceError:
        _t = "R3"
        log.info("%s: %s" % (_t, sys.exc_info()[1]))
   #callable = bool(getattr(refobj, '__call__', None))
    if type(obj) is CallableProxyType: callable = True
    else: callable = False
    pickler.save_reduce(_create_weakproxy, (refobj, callable), obj=obj)
    log.info("# %s" % _t)
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

@register(ModuleType)
def save_module(pickler, obj):
    if False: #_use_diff:
        if obj.__name__.split('.', 1)[0] != "dill":
            try:
                changed = diff.whats_changed(obj, seen=pickler._diff_cache)[0]
            except RuntimeError:  # not memorised module, probably part of dill
                pass
            else:
                log.info("M2: %s with diff" % obj)
                log.info("Diff: %s", changed.keys())
                pickler.save_reduce(_import_module, (obj.__name__,), obj=obj,
                                    state=changed)
                log.info("# M2")
                return

        log.info("M1: %s" % obj)
        pickler.save_reduce(_import_module, (obj.__name__,), obj=obj)
        log.info("# M1")
    else:
        builtin_mod = _is_builtin_module(obj)
        if obj.__name__ not in ("builtins", "dill", "dill._dill") and not builtin_mod or \
                is_dill(pickler, child=True) and obj is pickler._main:
            log.info("M1: %s" % obj)
            _main_dict = obj.__dict__.copy() #XXX: better no copy? option to copy?
            [_main_dict.pop(item, None) for item in singletontypes
                + ["__builtins__", "__loader__"]]
            pickler.save_reduce(_import_module, (obj.__name__,), obj=obj,
                                state=_main_dict)
            log.info("# M1")
        elif PY3 and obj.__name__ == "dill._dill":
            log.info("M2: %s" % obj)
            pickler.save_global(obj, name="_dill")
            log.info("# M2")
        else:
            log.info("M2: %s" % obj)
            pickler.save_reduce(_import_module, (obj.__name__,), obj=obj)
            log.info("# M2")
        return
    return

@register(TypeType)
def save_type(pickler, obj, postproc_list=None):
    if obj in _typemap:
        log.info("T1: %s" % obj)
        pickler.save_reduce(_load_type, (_typemap[obj],), obj=obj)
        log.info("# T1")
    elif obj.__bases__ == (tuple,) and all([hasattr(obj, attr) for attr in ('_fields','_asdict','_make','_replace')]):
        # special case: namedtuples
        log.info("T6: %s" % obj)
        if OLD37 or (not obj._field_defaults):
            pickler.save_reduce(_create_namedtuple, (obj.__name__, obj._fields, obj.__module__), obj=obj)
        else:
            defaults = [obj._field_defaults[field] for field in obj._fields if field in obj._field_defaults]
            pickler.save_reduce(_create_namedtuple, (obj.__name__, obj._fields, obj.__module__, defaults), obj=obj)
        log.info("# T6")
        return

    # special cases: NoneType, NotImplementedType, EllipsisType
    elif obj is type(None):
        log.info("T7: %s" % obj)
        #XXX: pickler.save_reduce(type, (None,), obj=obj)
        if PY3:
            pickler.write(bytes('c__builtin__\nNoneType\n', 'UTF-8'))
        else:
            pickler.write('c__builtin__\nNoneType\n')
        log.info("# T7")
    elif obj is NotImplementedType:
        log.info("T7: %s" % obj)
        pickler.save_reduce(type, (NotImplemented,), obj=obj)
        log.info("# T7")
    elif obj is EllipsisType:
        log.info("T7: %s" % obj)
        pickler.save_reduce(type, (Ellipsis,), obj=obj)
        log.info("# T7")

    else:
        obj_name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
        _byref = getattr(pickler, '_byref', None)
        obj_recursive = id(obj) in getattr(pickler, '_postproc', ())
        incorrectly_named = not _locate_function(obj, pickler)
        if not _byref and not obj_recursive and incorrectly_named: # not a function, but the name was held over
            if issubclass(type(obj), type):
                # thanks to Tom Stepleton pointing out pickler._session unneeded
                _t = 'T2'
                log.info("%s: %s" % (_t, obj))
                _dict = _dict_from_dictproxy(obj.__dict__)
            else:
                _t = 'T3'
                log.info("%s: %s" % (_t, obj))
                _dict = obj.__dict__
           #print (_dict)
           #print ("%s\n%s" % (type(obj), obj.__name__))
           #print ("%s\n%s" % (obj.__bases__, obj.__dict__))
            for name in _dict.get("__slots__", []):
                del _dict[name]
            if PY3 and obj_name != obj.__name__:
                if postproc_list is None:
                    postproc_list = []
                postproc_list.append((setattr, (obj, '__qualname__', obj_name)))
            _save_with_postproc(pickler, (_create_type, (
                type(obj), obj.__name__, obj.__bases__, _dict
            )), obj=obj, postproc_list=postproc_list)
            log.info("# %s" % _t)
        else:
            log.info("T4: %s" % obj)
            if incorrectly_named:
                warnings.warn('Cannot locate reference to %r.' % (obj,), PicklingWarning)
            if obj_recursive:
                warnings.warn('Cannot pickle %r: %s.%s has recursive self-references that trigger a RecursionError.' % (obj, obj.__module__, obj_name), PicklingWarning)
           #print (obj.__dict__)
           #print ("%s\n%s" % (type(obj), obj.__name__))
           #print ("%s\n%s" % (obj.__bases__, obj.__dict__))
            StockPickler.save_global(pickler, obj, name=obj_name)
            log.info("# T4")
    return

# Error in PyPy 2.7 when adding ABC support
if IS_PYPY2:
    @register(FrameType)
    def save_frame(pickler, obj):
        raise PicklingError('Cannot pickle a Python stack frame')

@register(property)
def save_property(pickler, obj):
    log.info("Pr: %s" % obj)
    pickler.save_reduce(property, (obj.fget, obj.fset, obj.fdel, obj.__doc__),
                        obj=obj)
    log.info("# Pr")

@register(staticmethod)
@register(classmethod)
def save_classmethod(pickler, obj):
    log.info("Cm: %s" % obj)
    im_func = '__func__' if PY3 else 'im_func'
    try:
        orig_func = getattr(obj, im_func)
    except AttributeError:  # Python 2.6
        orig_func = obj.__get__(None, object)
        if isinstance(obj, classmethod):
            orig_func = getattr(orig_func, im_func) # Unbind

    # if PY3:
    #     if type(obj.__dict__) is dict:
    #         if obj.__dict__:
    #             state = obj.__dict__
    #         else:
    #             state = None
    #     else:
    #         state = (None, {'__dict__', obj.__dict__})
    # else:
    #     state = None

    pickler.save_reduce(type(obj), (orig_func,), obj=obj)
    log.info("# Cm")

@register(FunctionType)
def save_function(pickler, obj):
    if not _locate_function(obj, pickler):
        log.info("F1: %s" % obj)
        _recurse = getattr(pickler, '_recurse', None)
        _byref = getattr(pickler, '_byref', None)
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
            globs_copy = obj.__globals__ if PY3 else obj.func_globals

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
            if PY3:
                glob_ids = {id(g) for g in globs_copy.values()}
            else:
                glob_ids = {id(g) for g in globs_copy.itervalues()}
            for stack_element in _postproc:
                if stack_element in glob_ids:
                    _postproc[stack_element].append((_setitems, (globs, globs_copy)))
                    break
            else:
                postproc_list.append((_setitems, (globs, globs_copy)))

        if PY3:
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
        else:
            closure = obj.func_closure
            if obj.__doc__ is not None:
                postproc_list.append((setattr, (obj, '__doc__', obj.__doc__)))
            if '__name__' not in globs or obj.__module__ != globs['__name__']:
                postproc_list.append((setattr, (obj, '__module__', obj.__module__)))
            if obj.__dict__:
                postproc_list.append((setattr, (obj, '__dict__', obj.__dict__)))

            _save_with_postproc(pickler, (_create_function, (
                obj.func_code, globs, obj.func_name, obj.func_defaults,
                closure
            )), obj=obj, postproc_list=postproc_list)

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
                    if PY3:
                        pickler.write(bytes('0', 'UTF-8'))
                    else:
                        pickler.write('0')

        log.info("# F1")
    else:
        log.info("F2: %s" % obj)
        name = getattr(obj, '__qualname__', getattr(obj, '__name__', None))
        StockPickler.save_global(pickler, obj, name=name)
        log.info("# F2")
    return

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
    if (child is False) or PY34 or (not hasattr(pickler.__class__, 'mro')):
        return 'dill' in pickler.__module__
    return Pickler in pickler.__class__.mro()

def _extend():
    """extend pickle with all of dill's registered types"""
    # need to have pickle not choke on _main_module?  use is_dill(pickler)
    for t,func in Pickler.dispatch.items():
        try:
            StockPickler.dispatch[t] = func
        except: #TypeError, PicklingError, UnpicklingError
            log.info("skip: %s" % t)
        else: pass
    return

del diff, _use_diff, use_diff

# EOF
