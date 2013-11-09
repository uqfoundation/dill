# -*- coding: utf-8 -*-
"""
dill: a utility for serialization of python objects

Based on code written by Oren Tirosh and Armin Ronacher.
Extended to a (near) full set of the builtin types (in types module),
and coded to the pickle interface, by <mmckerns@caltech.edu>.
Initial port to python3 by Jonathan Dobson, continued by mmckerns.
Test against "all" python types (Std. Lib. CH 1-15 @ 2.7) by mmckerns.
Test against CH16+ Std. Lib. ... TBD.
"""
__all__ = ['dump','dumps','load','loads','dump_session','load_session',\
           'Pickler','Unpickler','register','copy','pickle','pickles',\
           'HIGHEST_PROTOCOL','PicklingError','UnpicklingError']

import logging
log = logging.getLogger("dill")
log.addHandler(logging.StreamHandler())
def _trace(boolean):
    """print a trace through the stack when pickling; useful for debugging"""
    if boolean: log.setLevel(logging.DEBUG)
    else: log.setLevel(logging.WARN)
    return

import os
import sys
PYTHON3 = (hex(sys.hexversion) >= '0x30000f0')
if PYTHON3: #XXX: get types from dill.objtypes ?
    import builtins as __builtin__
    from pickle import _Pickler as StockPickler, _Unpickler as StockUnpickler
    from _thread import LockType
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
    DictProxyType = type(object.__dict__)
else:
    import __builtin__
    from pickle import Pickler as StockPickler, Unpickler as StockUnpickler
    from thread import LockType
    from types import CodeType, FunctionType, ClassType, MethodType, \
         GeneratorType, DictProxyType, XRangeType, SliceType, TracebackType, \
         NotImplementedType, EllipsisType, FrameType, ModuleType, \
         BufferType, BuiltinMethodType, TypeType
from pickle import HIGHEST_PROTOCOL, PicklingError, UnpicklingError
import __main__ as _main_module
import marshal
import gc
# import zlib
from weakref import ReferenceType, ProxyType, CallableProxyType
from functools import partial
from operator import itemgetter, attrgetter
# new in python2.5
if hex(sys.hexversion) >= '0x20500f0':
    from types import MemberDescriptorType, GetSetDescriptorType
try:
    import ctypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False
try:
    from numpy import ufunc as NumpyUfuncType
except ImportError:
    NumpyUfuncType = None

# make sure to add these 'hand-built' types to _typemap
if PYTHON3:
    CellType = type((lambda x: lambda y: x)(0).__closure__[0])
else:
    CellType = type((lambda x: lambda y: x)(0).func_closure[0])
WrapperDescriptorType = type(type.__repr__)
MethodDescriptorType = type(type.__dict__['mro'])
MethodWrapperType = type([].__repr__)
PartialType = type(partial(int,base=2))
SuperType = type(super(Exception, TypeError()))
ItemGetterType = type(itemgetter(0))
AttrGetterType = type(attrgetter('__repr__'))
FileType = open(os.devnull, 'rb', buffering=0)
TextWrapperType = open(os.devnull, 'r', buffering=-1)
BufferedRandomType = open(os.devnull, 'r+b', buffering=-1)
BufferedReaderType = open(os.devnull, 'rb', buffering=-1)
BufferedWriterType = open(os.devnull, 'wb', buffering=-1)
try:
    from cStringIO import StringIO, InputType, OutputType
except ImportError:
    if PYTHON3:
        from io import BytesIO as StringIO
    else:
        from StringIO import StringIO
    InputType = OutputType = None
try:
    __IPYTHON__ is True # is ipython
    ExitType = None     # IPython.core.autocall.ExitAutocall
    singletontypes = ['exit', 'quit', 'get_ipython']
except NameError:
    ExitType = type(exit)
    singletontypes = []

### Shorthands (modified from python2.5/lib/pickle.py)
def copy(obj):
    """use pickling to 'copy' an object"""
    return loads(dumps(obj))

def dump(obj, file, protocol=HIGHEST_PROTOCOL):
    """pickle an object to a file"""
    pik = Pickler(file, protocol)
    pik._main_module = _main_module
    pik.dump(obj)
    return

def dumps(obj, protocol=HIGHEST_PROTOCOL):
    """pickle an object to a string"""
    file = StringIO()
    dump(obj, file, protocol)
    return file.getvalue()

def load(file):
    """unpickle an object from a file"""
    pik = Unpickler(file)
    pik._main_module = _main_module
    obj = pik.load()
   #_main_module.__dict__.update(obj.__dict__) #XXX: should update globals ?
    return obj

def loads(str):
    """unpickle an object from a string"""
    file = StringIO(str)
    return load(file)

# def dumpzs(obj, protocol=HIGHEST_PROTOCOL):
#     """pickle an object to a compressed string"""
#     return zlib.compress(dumps(obj, protocol))

# def loadzs(str):
#     """unpickle an object from a compressed string"""
#     return loads(zlib.decompress(str))

### End: Shorthands ###

### Pickle the Interpreter Session
def dump_session(filename='/tmp/session.pkl', main_module=_main_module):
    """pickle the current state of __main__ to a file"""
    f = file(filename, 'wb')
    try:
        pickler = Pickler(f, 2)
        pickler._main_module = main_module
        pickler._session = True # is best indicator of when pickling a session
        pickler.dump(main_module)
        pickler._session = False
    finally:
        f.close()
    return

def load_session(filename='/tmp/session.pkl', main_module=_main_module):
    """update the __main__ module with the state from the session file"""
    f = file(filename, 'rb')
    try:
        unpickler = Unpickler(f)
        unpickler._main_module = main_module
        unpickler._session = True
        module = unpickler.load()
        unpickler._session = False
        main_module.__dict__.update(module.__dict__)
    finally:
        f.close()
    return

### End: Pickle the Interpreter

### Extend the Picklers
class Pickler(StockPickler):
    """python's Pickler extended to interpreter sessions"""
    dispatch = StockPickler.dispatch.copy()
    _main_module = None
    _session = False
    pass

class Unpickler(StockUnpickler):
    """python's Unpickler extended to interpreter sessions and more types"""
    _main_module = None
    _session = False

    def find_class(self, module, name):
        if (module, name) == ('__builtin__', '__main__'):
            return self._main_module.__dict__ #XXX: above set w/save_module_dict
        return StockUnpickler.find_class(self, module, name)
    pass

'''
def dispatch_table():
    """get the dispatch table of registered types"""
    return Pickler.dispatch
'''

def pickle(t, func):
    """expose dispatch table for user-created extensions"""
    Pickler.dispatch[t] = func
    return

def register(t):
    def proxy(func):
        Pickler.dispatch[t] = func
        return func
    return proxy

def _create_typemap():
    import types
    if PYTHON3:
        d = dict(list(__builtin__.__dict__.items()) + \
                 list(types.__dict__.items())).items()
        builtin = 'builtins'
    else:
        d = types.__dict__.iteritems()
        builtin = '__builtin__'
    for key, value in d:
        if getattr(value, '__module__', None) == builtin \
        and type(value) is type:
            yield value, key
    return
_typemap = dict(_create_typemap())
_typemap.update({
    CellType: 'CellType',
    WrapperDescriptorType: 'WrapperDescriptorType',
    MethodDescriptorType: 'MethodDescriptorType',
    MethodWrapperType: 'MethodWrapperType',
    PartialType: 'PartialType',
    SuperType: 'SuperType',
    ItemGetterType: 'ItemGetterType',
    AttrGetterType: 'AttrGetterType',
    FileType: 'FileType',
    BufferedRandomType: 'BufferedRandomType',
    BufferedReaderType: 'BufferedReaderType',
    BufferedWriterType: 'BufferedWriterType',
    TextWrapperType: 'TextWrapperType',
})
if ExitType:
    _typemap[ExitType] = 'ExitType'
if InputType:
    _typemap[InputType] = 'InputType'
    _typemap[OutputType] = 'OutputType'
if PYTHON3:
    _reverse_typemap = dict((v, k) for k, v in _typemap.items())
else:
    _reverse_typemap = dict((v, k) for k, v in _typemap.iteritems())

def _unmarshal(string):
    return marshal.loads(string)

def _load_type(name):
    return _reverse_typemap[name]

def _create_type(typeobj, *args):
    return typeobj(*args)

def _create_ftype(ftypeobj, func, args, kwds):
    return ftypeobj(func, *args, **kwds)

def _create_lock(locked, *args):
    from threading import Lock
    lock = Lock()
    if locked:
        if not lock.acquire(False):
            raise UnpicklingError("Cannot acquire lock")
    return lock

def _create_filehandle(name, mode, position, closed): # buffering=0
    # only pickles the handle, not the file contents... good? or StringIO(data)?
    # (for file contents see: http://effbot.org/librarybook/copy-reg.htm)
    # NOTE: handle special cases first (are there more special cases?)
    names = {'<stdin>':sys.__stdin__, '<stdout>':sys.__stdout__,
             '<stderr>':sys.__stderr__} #XXX: better fileno=(0,1,2) ?
    if name in list(names.keys()): f = names[name] #XXX: safer "f=sys.stdin"
    elif name == '<tmpfile>': import os; f = os.tmpfile()
    elif name == '<fdopen>': import tempfile; f = tempfile.TemporaryFile(mode)
    else:
        try: # try to open the file by name   # NOTE: has different fileno
            f = open(name, mode)#FIXME: missing: *buffering*, encoding,softspace
        except IOError: 
            err = sys.exc_info()[1]
            try: # failing, then use /dev/null #XXX: better to just fail here?
                import os; f = open(os.devnull, mode)
            except IOError:
                raise UnpicklingError(err)
                #XXX: python default is closed '<uninitialized file>' file/mode
    if closed: f.close()
    else: f.seek(position)
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

if HAS_CTYPES:
    ctypes.pythonapi.PyCell_New.restype = ctypes.py_object
    ctypes.pythonapi.PyCell_New.argtypes = [ctypes.py_object]
    # thanks to Paul Kienzle for cleaning the ctypes CellType logic
    def _create_cell(contents):
        return ctypes.pythonapi.PyCell_New(contents)

def _create_weakref(obj, *args):
    from weakref import ref
    if obj is None: # it's dead
        if PYTHON3:
            from collections import UserDict
        else:
            from UserDict import UserDict
        return ref(UserDict(), *args)
    return ref(obj, *args)

def _create_weakproxy(obj, callable=False, *args):
    from weakref import proxy
    if obj is None: # it's dead
        if callable: return proxy(lambda x:x, *args)
        if PYTHON3:
            from collections import UserDict
        else:
            from UserDict import UserDict
        return proxy(UserDict(), *args)
    return proxy(obj, *args)

def _eval_repr(repr_str):
    return eval(repr_str)

def _getattr(objclass, name, repr_str):
    # hack to grab the reference directly
    try: #XXX: works only for __builtin__ ?
        attr = repr_str.split("'")[3]
        return eval(attr+'.__dict__["'+name+'"]')
    except:
        attr = getattr(objclass,name)
        if name == '__dict__':
            attr = attr[name]
        return attr

def _get_attr(self, name):
    # stop recursive pickling
    return getattr(self, name)

def _dict_from_dictproxy(dictproxy):
    _dict = dictproxy.copy() # convert dictproxy to dict
    _dict.pop('__dict__', None)
    _dict.pop('__weakref__', None)
    return _dict

def _import_module(import_name):
    if '.' in import_name:
        items = import_name.split('.')
        module = '.'.join(items[:-1])
        obj = items[-1]
    else:
        return __import__(import_name)
    return getattr(__import__(module, None, None, [obj]), obj)

def _locate_function(obj, session=False):
    if obj.__module__ == '__main__': # and session:
        return False
    try:
        found = _import_module(obj.__module__ + '.' + obj.__name__)
    except:
        return False
    return found is obj

@register(CodeType)
def save_code(pickler, obj):
    log.info("Co: %s" % obj)
    pickler.save_reduce(_unmarshal, (marshal.dumps(obj),), obj=obj)
    return

@register(FunctionType)
def save_function(pickler, obj):
    if not _locate_function(obj): #, pickler._session):
        log.info("F1: %s" % obj)
        if PYTHON3:
            pickler.save_reduce(FunctionType, (obj.__code__, obj.__globals__,
                                               obj.__name__, obj.__defaults__,
                                               obj.__closure__), obj=obj)
        else:
            pickler.save_reduce(FunctionType, (obj.func_code, obj.func_globals,
                                               obj.func_name, obj.func_defaults,
                                               obj.func_closure), obj=obj)
    else:
        log.info("F2: %s" % obj)
        StockPickler.save_global(pickler, obj)
    return

@register(dict)
def save_module_dict(pickler, obj):
    if is_dill(pickler) and obj is pickler._main_module.__dict__:
        log.info("D1: <dict%s" % str(obj.__repr__).split('dict')[-1]) # obj
        if PYTHON3:
            pickler.write(bytes('c__builtin__\n__main__\n', 'UTF-8'))
        else:
            pickler.write('c__builtin__\n__main__\n')
    elif not is_dill(pickler) and obj is _main_module.__dict__:
        log.info("D3: <dict%s" % str(obj.__repr__).split('dict')[-1]) # obj
        if PYTHON3:
            pickler.write(bytes('c__main__\n__dict__\n', 'UTF-8'))
        else:
            pickler.write('c__main__\n__dict__\n')   #XXX: works in general?
    else:
        log.info("D2: <dict%s" % str(obj.__repr__).split('dict')[-1]) # obj
        StockPickler.save_dict(pickler, obj)
    return

@register(ClassType)
def save_classobj(pickler, obj):
    if obj.__module__ == '__main__':
        log.info("C1: %s" % obj)
        pickler.save_reduce(ClassType, (obj.__name__, obj.__bases__,
                                        obj.__dict__), obj=obj)
                                       #XXX: or obj.__dict__.copy()), obj=obj) ?
    else:
        log.info("C2: %s" % obj)
        StockPickler.save_global(pickler, obj)
    return

@register(LockType)
def save_lock(pickler, obj):
    log.info("Lo: %s" % obj)
    pickler.save_reduce(_create_lock, (obj.locked(),), obj=obj)
    return

@register(ItemGetterType)
def save_itemgetter(pickler, obj):
    log.info("Ig: %s" % obj)
    helper = _itemgetter_helper()
    obj(helper)
    pickler.save_reduce(type(obj), tuple(helper.items), obj=obj)
    return

@register(AttrGetterType)
def save_attrgetter(pickler, obj):
    log.info("Ag: %s" % obj)
    attrs = []
    helper = _attrgetter_helper(attrs)
    obj(helper)
    pickler.save_reduce(type(obj), tuple(attrs), obj=obj)
    return

# __getstate__ explicitly added to raise TypeError when pickling:
# http://www.gossamer-threads.com/lists/python/bugs/871199
@register(FileType) #XXX: in 3.x has buffer=0, needs different _create?
@register(BufferedRandomType)
@register(BufferedReaderType)
@register(BufferedWriterType)
@register(TextWrapperType)
def save_file(pickler, obj):
    log.info("Fi: %s" % obj)
    if obj.closed:
        position = None
    else:
        position = obj.tell()
    pickler.save_reduce(_create_filehandle, (obj.name, obj.mode, position, \
                                             obj.closed), obj=obj)
    return

# The following two functions are based on 'saveCStringIoInput'
# and 'saveCStringIoOutput' from spickle
# Copyright (c) 2011 by science+computing ag
# License: http://www.apache.org/licenses/LICENSE-2.0
if InputType:
    @register(InputType)
    def save_stringi(pickler, obj):
        log.info("Io: %s" % obj)
        if obj.closed:
            value = ''; position = None
        else:
            value = obj.getvalue(); position = obj.tell()
        pickler.save_reduce(_create_stringi, (value, position, \
                                              obj.closed), obj=obj)
        return

    @register(OutputType)
    def save_stringo(pickler, obj):
        log.info("Io: %s" % obj)
        if obj.closed:
            value = ''; position = None
        else:
            value = obj.getvalue(); position = obj.tell()
        pickler.save_reduce(_create_stringo, (value, position, \
                                              obj.closed), obj=obj)
        return

@register(PartialType)
def save_functor(pickler, obj):
    log.info("Fu: %s" % obj)
    pickler.save_reduce(_create_ftype, (type(obj), obj.func, obj.args,
                                        obj.keywords), obj=obj)
    return

@register(SuperType)
def save_functor(pickler, obj):
    log.info("Su: %s" % obj)
    pickler.save_reduce(super, (obj.__thisclass__, obj.__self__), obj=obj)
    return

@register(BuiltinMethodType)
def save_builtin_method(pickler, obj):
    if obj.__self__ is not None:
        log.info("B1: %s" % obj)
        pickler.save_reduce(_get_attr, (obj.__self__, obj.__name__), obj=obj)
    else:
        log.info("B2: %s" % obj)
        StockPickler.save_global(pickler, obj)
    return

@register(MethodType) #FIXME: fails for 'hidden' or 'name-mangled' classes
def save_instancemethod0(pickler, obj):# example: cStringIO.StringI
    log.info("Me: %s" % obj)
    if PYTHON3:
        pickler.save_reduce(MethodType, (obj.__func__, obj.__self__), obj=obj)
    else:
        pickler.save_reduce(MethodType, (obj.im_func, obj.im_self,
                                         obj.im_class), obj=obj)
    return

if hex(sys.hexversion) >= '0x20500f0':
    @register(MemberDescriptorType)
    @register(GetSetDescriptorType)
    @register(MethodDescriptorType)
    @register(WrapperDescriptorType)
    def save_wrapper_descriptor(pickler, obj):
        log.info("Wr: %s" % obj)
        pickler.save_reduce(_getattr, (obj.__objclass__, obj.__name__,
                                       obj.__repr__()), obj=obj)
        return

    @register(MethodWrapperType)
    def save_instancemethod(pickler, obj):
        log.info("Mw: %s" % obj)
        pickler.save_reduce(getattr, (obj.__self__, obj.__name__), obj=obj)
        return
else:
    @register(MethodDescriptorType)
    @register(WrapperDescriptorType)
    def save_wrapper_descriptor(pickler, obj):
        log.info("Wr: %s" % obj)
        pickler.save_reduce(_getattr, (obj.__objclass__, obj.__name__,
                                       obj.__repr__()), obj=obj)
        return

if HAS_CTYPES:
    @register(CellType)
    def save_cell(pickler, obj):
        log.info("Ce: %s" % obj)
        pickler.save_reduce(_create_cell, (obj.cell_contents,), obj=obj)
        return
 
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
        pickler.save_reduce(getattr, (attr.__objclass__, "__dict__"), obj=obj)
        return
    # all bad below... so throw ReferenceError or TypeError
    from weakref import ReferenceError
    raise ReferenceError("%s does not reference a class __dict__" % obj)

@register(SliceType)
def save_slice(pickler, obj):
    log.info("Sl: %s" % obj)
    pickler.save_reduce(slice, (obj.start, obj.stop, obj.step), obj=obj)
    return

@register(XRangeType)
@register(EllipsisType)
@register(NotImplementedType)
def save_singleton(pickler, obj):
    log.info("Si: %s" % obj)
    pickler.save_reduce(_eval_repr, (obj.__repr__(),), obj=obj)
    return

# thanks to Paul Kienzle for pointing out ufuncs didn't pickle
if NumpyUfuncType:
    @register(NumpyUfuncType)
    def save_numpy_ufunc(pickler, obj):
        log.info("Nu: %s" % obj)
        StockPickler.save_global(pickler, obj)
        return
# NOTE: the above 'save' performs like:
#   import copy_reg
#   def udump(f): return f.__name__
#   def uload(name): return getattr(numpy, name)
#   copy_reg.pickle(NumpyUfuncType, udump, uload)

def _proxy_helper(obj): # a dead proxy returns a reference to None
    # get memory address of proxy's reference object
    address = int(repr(obj).rstrip('>').split(' at ')[-1], base=16)
    return address

def _locate_object(address, module=None):
    # get the object located at the given memory address
    special = [None, True, False] #XXX: more...?
    for obj in special:
        if address == id(obj): return obj
    if module:
        if PYTHON3:
            objects = iter(module.__dict__.values())
        else:
            objects = module.__dict__.itervalues()
    else: objects = iter(gc.get_objects())
    for obj in objects:
        if address == id(obj): return obj
    # all bad below... nothing found so throw ReferenceError or TypeError
    from weakref import ReferenceError
    try: address = hex(address)
    except TypeError:
        raise TypeError("'%s' is not a valid memory address" % str(address))
    raise ReferenceError("Cannot reference object at '%s'" % address)

@register(ReferenceType)
def save_weakref(pickler, obj):
    refobj = obj()
    log.info("Rf: %s" % obj)
   #refobj = ctypes.pythonapi.PyWeakref_GetObject(obj) # dead returns "None"
    pickler.save_reduce(_create_weakref, (refobj,), obj=obj)
    return

@register(ProxyType)
@register(CallableProxyType)
def save_weakproxy(pickler, obj):
    refobj = _locate_object(_proxy_helper(obj))
    try: log.info("Rf: %s" % obj)
    except ReferenceError: log.info("Rf: %s" % sys.exc_info()[1])
   #callable = bool(getattr(refobj, '__call__', None))
    if type(obj) is CallableProxyType: callable = True
    else: callable = False
    pickler.save_reduce(_create_weakproxy, (refobj, callable), obj=obj)
    return

@register(ModuleType)
def save_module(pickler, obj):
    if is_dill(pickler) and obj is pickler._main_module:
        log.info("M1: %s" % obj)
        _main_dict = obj.__dict__.copy()
        [_main_dict.pop(item,None) for item in singletontypes]
        pickler.save_reduce(__import__, (obj.__name__,), obj=obj,
                            state=_main_dict)
    else:
        log.info("M2: %s" % obj)
        pickler.save_reduce(_import_module, (obj.__name__,), obj=obj)
    return

@register(type)
def save_type(pickler, obj):
    if obj in _typemap:
        log.info("T1: %s" % obj)
        pickler.save_reduce(_load_type, (_typemap[obj],), obj=obj)
    elif obj.__module__ == '__main__':
        if type(obj) == type:
            # we are pickling the interpreter
            if is_dill(pickler): # and pickler._session:
                # thanks to Tom Stepleton pointing out pickler._session unneeded
                log.info("T2: %s" % obj)
                _dict = _dict_from_dictproxy(obj.__dict__)
            else: # otherwise punt to StockPickler
                log.info("T5: %s" % obj)
                StockPickler.save_global(pickler, obj)
                return
        else:
            log.info("T3: %s" % obj)
            _dict = obj.__dict__
       #print (_dict)
       #print ("%s\n%s" % (type(obj), obj.__name__))
       #print ("%s\n%s" % (obj.__bases__, obj.__dict__))
        pickler.save_reduce(_create_type, (type(obj), obj.__name__,
                                           obj.__bases__, _dict), obj=obj)
    else:
        log.info("T4: %s" % obj)
       #print (obj.__dict__)
       #print ("%s\n%s" % (type(obj), obj.__name__))
       #print ("%s\n%s" % (obj.__bases__, obj.__dict__))
        StockPickler.save_global(pickler, obj)
    return

# quick sanity checking
def pickles(obj,exact=False):
    """quick check if object pickles with dill"""
    try:
        pik = copy(obj)
        if exact:
            return pik == obj
        return type(pik) == type(obj)
    except (TypeError, AssertionError, PicklingError, UnpicklingError):
        return False

# use to protect against missing attributes
def is_dill(pickler):
    "check the dill-ness of your pickler"
    return 'dill' in pickler.__module__
   #return hasattr(pickler,'_main_module')

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

# EOF
