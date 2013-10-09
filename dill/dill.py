# -*- coding: utf-8 -*-
"""
dill: a utility for serialization of python objects

Based on code written by Oren Tirosh and Armin Ronacher.
Extended to a (near) full set of python types (in types module),
and coded to the pickle interface, by mmckerns@caltech.edu
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

import __builtin__
import __main__ as _main_module
import sys
import marshal
# import zlib
from pickle import HIGHEST_PROTOCOL, PicklingError, UnpicklingError
from pickle import Pickler as StockPickler
from pickle import Unpickler as StockUnpickler
from types import CodeType, FunctionType, ClassType, MethodType, \
     GeneratorType, DictProxyType, XRangeType, SliceType, TracebackType, \
     NotImplementedType, EllipsisType, FrameType, ModuleType, \
     BuiltinMethodType, TypeType
from weakref import ReferenceType, ProxyType, CallableProxyType
from thread import LockType
from functools import partial
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

# make sure to add these 'hand-built' types to _typedict
CellType = type((lambda x: lambda y: x)(0).func_closure[0])
WrapperDescriptorType = type(type.__repr__)
MethodDescriptorType = type(type.__dict__['mro'])
MethodWrapperType = type([].__repr__)
PartialType = type(partial(int,base=2))
try:
    __IPYTHON__ is True # is ipython
    ExitType = None     # IPython.core.autocall.ExitAutocall
    singletontypes = ['exit', 'quit', 'get_ipython']
except NameError:
    ExitType = type(exit)
    singletontypes = []

### Shorthands (modified from python2.5/lib/pickle.py)
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

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
    for key, value in types.__dict__.iteritems():
        if getattr(value, '__module__', None) == '__builtin__' and \
           type(value) is type:
            yield value, key
    return
_typedict = {
    CellType:                   'CellType',
    WrapperDescriptorType:      'WrapperDescriptorType',
    MethodDescriptorType:       'MethodDescriptorType',
    MethodWrapperType:          'MethodWrapperType',
    PartialType:                'PartialType',
}
if ExitType:
    _typedict[ExitType] = 'ExitType'
_typemap = dict(_create_typemap(), **_typedict)
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
            raise UnpicklingError, "Cannot acquire lock"
    return lock

if HAS_CTYPES:
    ctypes.pythonapi.PyCell_New.restype = ctypes.py_object
    ctypes.pythonapi.PyCell_New.argtypes = [ctypes.py_object]
    # thanks to Paul Kienzle for cleaning the ctypes CellType logic
    def _create_cell(contents):
        return ctypes.pythonapi.PyCell_New(contents)

    ctypes.pythonapi.PyDictProxy_New.restype = ctypes.py_object
    ctypes.pythonapi.PyDictProxy_New.argtypes = [ctypes.py_object]
    def _create_dictproxy(dictobj, *args):
        dprox = ctypes.pythonapi.PyDictProxy_New(dictobj)
        #XXX: hack to take care of pickle 'nesting' the correct dictproxy
        if 'nested' in args and type(dprox['__dict__']) == DictProxyType:
            return dprox['__dict__']
        return dprox

    ctypes.pythonapi.PyWeakref_GetObject.restype = ctypes.py_object
    ctypes.pythonapi.PyWeakref_GetObject.argtypes = [ctypes.py_object]
    def _create_weakref(obj, *args):
        from weakref import ref, ReferenceError
        if obj: return ref(obj) #XXX: callback?
        raise ReferenceError, "Cannot pickle reference to dead object"

def _create_weakproxy(obj, *args):
    from weakref import proxy, ReferenceError
    if obj: return proxy(obj) #XXX: callback?
    raise ReferenceError, "Cannot pickle reference to dead object"

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

def _dict_from_dictproxy(dictproxy):
    _dict = dictproxy.copy() # convert dictproxy to dict
    _dict.pop('__dict__')
    try: # new classes have weakref (while not all others do)
        _dict.pop('__weakref__')
    except KeyError:
        pass
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
        pickler.write('c__builtin__\n__main__\n')
    elif not is_dill(pickler) and obj is _main_module.__dict__:
        log.info("D3: <dict%s" % str(obj.__repr__).split('dict')[-1]) # obj
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

@register(PartialType)
def save_functor(pickler, obj):
    log.info("Fu: %s" % obj)
    pickler.save_reduce(_create_ftype, (type(obj), obj.func, obj.args,
                                        obj.keywords), obj=obj)
    return

@register(BuiltinMethodType)
def save_builtin_method(pickler, obj):
    if obj.__self__ is not None:
        log.info("B1: %s" % obj)
        pickler.save_reduce(getattr, (obj.__self__, obj.__name__), obj=obj)
    else:
        log.info("B2: %s" % obj)
        StockPickler.save_global(pickler, obj)
    return

if hex(sys.hexversion) >= '0x20600f0':
    @register(MethodWrapperType)
    @register(MethodType)
    def save_instancemethod(pickler, obj):
        log.info("Me: %s" % obj)
        pickler.save_reduce(getattr, (obj.__self__, obj.__name__), obj=obj)
        return
if hex(sys.hexversion) >= '0x20500f0':
    @register(MethodWrapperType)
    def save_instancemethod(pickler, obj):
        log.info("Me: %s" % obj)
        pickler.save_reduce(getattr, (obj.__self__, obj.__name__), obj=obj)
        return
    @register(MethodType) #FIXME: fails for 'hidden' or 'name-mangled' classes
    def save_instancemethod0(pickler, obj):# example: cStringIO.StringI
        log.info("Me: %s" % obj)
        pickler.save_reduce(MethodType, (obj.im_func, obj.im_self,
                                         obj.im_class), obj=obj)
        return
else:
    @register(MethodType) #FIXME: fails for 'hidden' or 'name-mangled' classes
    def save_instancemethod0(pickler, obj):# example: cStringIO.StringI
        log.info("Me: %s" % obj)
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

    @register(DictProxyType)
    def save_dictproxy(pickler, obj):
        log.info("Dp: %s" % obj)
        pickler.save_reduce(_create_dictproxy, (dict(obj),'nested'), obj=obj)
        return

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

def _locate_refobj(oid, module):
    for obj in module.__dict__.values():
        if oid == id(obj):
            return obj
    #XXX: nothing found... so return None? or Error?
    return None

"""
@register(ReferenceType)
def save_weakref(pickler, obj):
    #FIXME: creates a dead weak ref, need to preserve "refobj"
    pickler.save_reduce(_create_weakref, (obj(),), obj=obj)
    #FIXME: first need to locate the module the ref obj lives
  # refobj = _locate_refobj(obj.__hash__(), pickler._main_module )
  # pickler.save_reduce(_create_weakref, (refobj,), obj=obj)
    #FIXME: can lead to Segmentation Fault
   #ref_obj = ctypes.pythonapi.PyWeakref_GetObject(obj) # dead returns "None"
   #if ref_obj:
   #    pickler.save_reduce(_create_weakref, (ref_obj,), obj=obj)
   #else: # FIXME: dead referenced object will raise an error
   #    pickler.save_reduce(_create_weakref, (ref_obj,), obj=obj)
    return
"""

"""
@register(ProxyType)
@register(CallableProxyType)
def save_weakproxy(pickler, obj):
    ref_obj = ctypes.pythonapi.PyWeakref_GetObject(obj) # dead returns "None"
    if ref_obj:
        pickler.save_reduce(_create_weakproxy, (ref_obj,), obj=obj)
    else: # FIXME: dead referenced object will raise an error
        pickler.save_reduce(_create_weakproxy, (ref_obj,), obj=obj)
    return
"""

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
            if is_dill(pickler) and pickler._session:
                log.info("T2: %s" % obj)
                _dict = _dict_from_dictproxy(obj.__dict__)
            else: # otherwise punt to StockPickler
                log.info("T5: %s" % obj)
                StockPickler.save_global(pickler, obj)
                return
        else:
            log.info("T3: %s" % obj)
            _dict = obj.__dict__
       #print _dict
       #print "%s\n%s" % (type(obj), obj.__name__)
       #print "%s\n%s" % (obj.__bases__, obj.__dict__)
        pickler.save_reduce(_create_type, (type(obj), obj.__name__,
                                           obj.__bases__, _dict), obj=obj)
    else:
        log.info("T4: %s" % obj)
       #print obj.__dict__
       #print "%s\n%s" % (type(obj), obj.__name__)
       #print "%s\n%s" % (obj.__bases__, obj.__dict__)
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
    except (TypeError, AssertionError, PicklingError, UnpicklingError), err:
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
