#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Author: Anirudh Vegesana (avegesan@cs.stanford.edu)
# Copyright (c) 2021-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
Provides shims for compatibility between versions of dill and Python.

Compatibility shims should be provided in this file. Here are two simple example
use cases.

Deprecation of constructor function:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Assume that we were transitioning _import_module in _dill.py to
the builtin function importlib.import_module when present.

@move_to(_dill)
def _import_module(import_name):
    ... # code already in _dill.py

_import_module = Getattr(importlib, 'import_module', Getattr(_dill, '_import_module', None))

The code will attempt to find import_module in the importlib module. If not
present, it will use the _import_module function in _dill.

Emulate new Python behavior in older Python versions:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CellType.cell_contents behaves differently in Python 3.6 and 3.7. It is
read-only in Python 3.6 and writable and deletable in 3.7.

if _dill.OLD37 and _dill.HAS_CTYPES and ...:
    @move_to(_dill)
    def _setattr(object, name, value):
        if type(object) is _dill.CellType and name == 'cell_contents':
            _PyCell_Set.argtypes = (ctypes.py_object, ctypes.py_object)
            _PyCell_Set(object, value)
        else:
            setattr(object, name, value)
... # more cases below

_setattr = Getattr(_dill, '_setattr', setattr)

_dill._setattr will be used when present to emulate Python 3.7 functionality in
older versions of Python while defaulting to the standard setattr in 3.7+.

See this PR for the discussion that lead to this system:
https://github.com/uqfoundation/dill/pull/443
"""

from typing import NamedTuple
import inspect, sys

_dill = sys.modules['dill._dill']


class Reduce(object):
    """
    Reduce objects are wrappers used for compatibility enforcement during
    unpickle-time. They should only be used in calls to pickler.save and
    other Reduce objects. They are only evaluated within unpickler.load.

    Pickling a Reduce object makes the two implementations equivalent:

    pickler.save(Reduce(*reduction))

    pickler.save_reduce(*reduction, obj=reduction)
    """
    __slots__ = ['reduction']
    def __new__(cls, *reduction, **kwargs):
        """
        Args:
            *reduction: a tuple that matches the format given here:
              https://docs.python.org/3/library/pickle.html#object.__reduce__
            is_callable: a bool to indicate that the object created by
              unpickling `reduction` is callable. If true, the current Reduce
              is allowed to be used as the function in further save_reduce calls
              or Reduce objects.
        """
        is_callable = kwargs.get('is_callable', False) # Pleases Py2. Can be removed later
        if is_callable:
            self = object.__new__(_CallableReduce)
        else:
            self = object.__new__(Reduce)
        self.reduction = reduction
        return self
    def __repr__(self):
        return 'Reduce%s' % (self.reduction,)
    def __copy__(self):
        return self # pragma: no cover
    def __deepcopy__(self, memo):
        return self # pragma: no cover
    def __reduce__(self):
        return self.reduction
    def __reduce_ex__(self, protocol):
        return self.__reduce__()

class _CallableReduce(Reduce):
    # A version of Reduce for functions. Used to trick pickler.save_reduce into
    # thinking that Reduce objects of functions are themselves meaningful functions.
    def __call__(self, *args, **kwargs):
        reduction = self.__reduce__()
        func = reduction[0]
        f_args = reduction[1]
        obj = func(*f_args)
        return obj(*args, **kwargs)

__NO_DEFAULT = _dill.Sentinel('Getattr.NO_DEFAULT')

def Getattr(object, name, default=__NO_DEFAULT):
    """
    A Reduce object that represents the getattr operation. When unpickled, the
    Getattr will access an attribute 'name' of 'object' and return the value
    stored there. If the attribute doesn't exist, the default value will be
    returned if present.

    The following statements are equivalent:

    Getattr(collections, 'OrderedDict')
    Getattr(collections, 'spam', None)
    Getattr(*args)

    Reduce(getattr, (collections, 'OrderedDict'))
    Reduce(getattr, (collections, 'spam', None))
    Reduce(getattr, args)

    During unpickling, the first two will result in collections.OrderedDict and
    None respectively because the first attribute exists and the second one does
    not, forcing it to use the default value given in the third argument.
    """

    if default is Getattr.NO_DEFAULT:
        reduction = (getattr, (object, name))
    else:
        reduction = (getattr, (object, name, default))

    return Reduce(*reduction, is_callable=callable(default))

Getattr.NO_DEFAULT = __NO_DEFAULT
del __NO_DEFAULT

class _PythonVersionInfo_Base(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int
    hexversion: int

    def __int__(self):
        return self.hexversion

class PythonVersionInfo(_PythonVersionInfo_Base):
    '''
    A reconstructable version of sys.version_info
    '''
    def __new__(cls, major, minor, micro, releaselevel, serial):

        releaselevel_hex = {
            'alpha':     0xa0,
            'beta':      0xb0,
            'candidate': 0xc0,
            'final':     0xf0
        }[releaselevel]

        hexversion = (major << 24) + (minor << 16) + (micro << 8) + releaselevel_hex + serial
        return super().__new__(cls, major, minor, micro, releaselevel, serial, hexversion)

    @classmethod
    def current(cls):
        return cls(*sys.version_info, sys.hexversion)

    @classmethod
    def current_implementation(cls):
        return cls(*sys.implementation.version, sys.implementation.hexversion)

    @classmethod
    def from_hexversion(cls, hexversion: int):
        major = (hexversion & 0xff000000) >> 24
        minor = (hexversion & 0x00ff0000) >> 16
        micro = (hexversion & 0x0000ff00) >>  8

        releaselevel = {
            0xa0: 'alpha',
            0xb0: 'beta',
            0xc0: 'candidate',
            0xf0: 'final'
        }[hexversion & 0x000000f0]

        serial = hexversion & 0x0000000f
        return super().__new__(cls, major, minor, micro, releaselevel, serial, hexversion)


try:
    # Try to use a fancier version class to compare the dill version if available
    from packaging.version import Version
except:
    # A versioning class that can only be used for comparing dill versions
    class Version(tuple):
        __slots__ = ()
        def __new__(cls, version):
            v = version.split('.')
            if len(v) < 4:
                v = [*v, *([0] * (4 - len(v)))]
            else:
                v = list(v)
            if v[-1] == 'dev0':
                v[-1] = -1
            for i in range(len(v)):
                v[i] = int(v[i])
            return super().__new__(cls, v)


def move_to(module, name=None):
    def decorator(func):
        if name is None:
            fname = func.__name__
        else:
            fname = name
        module.__dict__[fname] = func
        func.__module__ = module.__name__
        return func
    return decorator

def register_shim(name, default):
    """
    A easier to understand and more compact way of "softly" defining a function.
    These two pieces of code are equivalent:

    if _dill.OLD3X:
        def _create_class():
            ...
    _create_class = register_shim('_create_class', types.new_class)

    if _dill.OLD3X:
        @move_to(_dill)
        def _create_class():
            ...
    _create_class = Getattr(_dill, '_create_class', types.new_class)

    Intuitively, it creates a function or object in the versions of dill/python
    that require special reimplementations, and use a core library or default
    implementation if that function or object does not exist.
    """
    func = globals().get(name)
    if func is not None:
        _dill.__dict__[name] = func
        func.__module__ = _dill.__name__

    if default is Getattr.NO_DEFAULT:
        reduction = (getattr, (_dill, name))
    else:
        reduction = (getattr, (_dill, name, default))

    return Reduce(*reduction, is_callable=callable(default))

######################
## Compatibility Shims are defined below
######################

_CELL_EMPTY = register_shim('_CELL_EMPTY', None)

if _dill.OLD37:
    if _dill.HAS_CTYPES and hasattr(_dill.ctypes, 'pythonapi') and hasattr(_dill.ctypes.pythonapi, 'PyCell_Set'):
        # CPython
        ctypes = _dill.ctypes

        _PyCell_Set = ctypes.pythonapi.PyCell_Set

        def _setattr(object, name, value):
            if type(object) is _dill.CellType and name == 'cell_contents':
                _PyCell_Set.argtypes = (ctypes.py_object, ctypes.py_object)
                _PyCell_Set(object, value)
            else:
                setattr(object, name, value)

        def _delattr(object, name):
            if type(object) is _dill.CellType and name == 'cell_contents':
                _PyCell_Set.argtypes = (ctypes.py_object, ctypes.c_void_p)
                _PyCell_Set(object, None)
            else:
                delattr(object, name)

    # General Python (not CPython) up to 3.6 is in a weird case, where it is
    # possible to pickle recursive cells, but we can't assign directly to the
    # cell.
    elif _dill.PY3:
        # Use nonlocal variables to reassign the cell value.
        # https://stackoverflow.com/a/59276835
        __nonlocal = ('nonlocal cell',)
        exec('''def _setattr(cell, name, value):
            if type(cell) is _dill.CellType and name == 'cell_contents':
                def cell_setter(value):
                    %s
                    cell = value # pylint: disable=unused-variable
                func = _dill.FunctionType(cell_setter.__code__, globals(), "", None, (cell,)) # same as cell_setter, but with cell being the cell's contents
                func(value)
            else:
                setattr(cell, name, value)''' % __nonlocal)

        exec('''def _delattr(cell, name):
            if type(cell) is _dill.CellType and name == 'cell_contents':
                try:
                    cell.cell_contents
                except:
                    return
                def cell_deleter():
                    %s
                    del cell # pylint: disable=unused-variable
                func = _dill.FunctionType(cell_deleter.__code__, globals(), "", None, (cell,)) # same as cell_deleter, but with cell being the cell's contents
                func()
            else:
                delattr(cell, name)''' % __nonlocal)

    else:
        # Likely PyPy 2.7. Simulate the nonlocal keyword with bytecode
        # manipulation.

        # The following function is based on 'cell_set' from 'cloudpickle'
        # https://github.com/cloudpipe/cloudpickle/blob/5d89947288a18029672596a4d719093cc6d5a412/cloudpickle/cloudpickle.py#L393-L482
        # Copyright (c) 2012, Regents of the University of California.
        # Copyright (c) 2009 `PiCloud, Inc. <http://www.picloud.com>`_.
        # License: https://github.com/cloudpipe/cloudpickle/blob/master/LICENSE
        def _setattr(cell, name, value):
            if type(cell) is _dill.CellType and name == 'cell_contents':
                _cell_set = _dill.FunctionType(
                      _cell_set_template_code, {}, '_cell_set', (), (cell,),)
                _cell_set(value)
            else:
                setattr(cell, name, value)

        def _cell_set_factory(value):
            lambda: cell
            cell = value

        co = _cell_set_factory.__code__

        _cell_set_template_code = _dill.CodeType(
            co.co_argcount,
            co.co_nlocals,
            co.co_stacksize,
            co.co_flags,
            co.co_code,
            co.co_consts,
            co.co_names,
            co.co_varnames,
            co.co_filename,
            co.co_name,
            co.co_firstlineno,
            co.co_lnotab,
            co.co_cellvars,  # co_freevars is initialized with co_cellvars
            (),  # co_cellvars is made empty
        )

        del co

        def _delattr(cell, name):
            if type(cell) is _dill.CellType and name == 'cell_contents':
                pass
            else:
                delattr(cell, name)

_setattr = register_shim('_setattr', setattr)
_delattr = register_shim('_delattr', delattr)
