#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Author: Anirudh Vegesana (avegesan@stanford.edu)
# Copyright (c) 2021 The Uncertainty Quantification Foundation.
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

@_assign_to_dill_module
def _import_module(import_name):
    ... # code already in _dill.py

_import_module = GetAttrShim(importlib, 'import_module', GetAttrShim(_dill, '_import_module', None))

The code will attempt to find import_module in the importlib module. If not
present, it will use the _import_module function in _dill.

Emulate new Python behavior in older Python versions:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CellType.cell_contents behaves differently in Python 3.6 and 3.7. It is
read-only in Python 3.6 and writable and deletable in 3.7.

if _dill.OLD37 and _dill.HAS_CTYPES and ...:
    @_assign_to_dill_module
    def _setattr(object, name, value):
        if type(object) is _dill.CellType and name == 'cell_contents':
            _PyCell_Set.argtypes = (ctypes.py_object, ctypes.py_object)
            _PyCell_Set(object, value)
        else:
            setattr(object, name, value)
... # more cases below

_setattr = GetAttrShim(_dill, '_setattr', setattr)

_dill._setattr will be used when present to emulate Python 3.7 functionality in
older versions of Python while defaulting to the standard setattr in 3.7+.

See this PR for the discussion that lead to this system:
https://github.com/uqfoundation/dill/pull/443
"""

import inspect, sys

_dill = sys.modules['dill._dill']


class Shim(object):
    """
    Shim objects are wrappers used for compatibility enforcement during
    unpickle-time. They should only be used in calls to pickler.save_reduce and
    other Shim objects. They are only evaluated within unpickler.load.
    """
    def __new__(cls, is_callable=False):
        if is_callable:
            if not hasattr(cls, '_Callable'):
                cls._Callable = type('_Callable', (_CallableShimMixin, cls), {})
            return object.__new__(cls._Callable)
        else:
            return object.__new__(cls)
    def __init__(self, reduction):
        super(Shim, self).__init__()
        self.reduction = reduction
    def __copy__(self):
        return self # pragma: no cover
    def __deepcopy__(self, memo):
        return self # pragma: no cover
    def __reduce__(self):
        return self.reduction
    def __reduce_ex__(self, protocol):
        return self.__reduce__()

class _CallableShimMixin(object):
    # A version of Shim for functions. Used to trick pickler.save_reduce into
    # thinking that Shim objects of functions are themselves meaningful functions.
    def __call__(self, *args, **kwargs):
        reduction = self.__reduce__()
        func = reduction[0]
        args = reduction[1]
        obj = func(args)
        return obj(*args, **kwargs)

class GetAttrShim(Shim):
    """
    A Shim object that represents the getattr operation. When unpickled, the
    GetAttrShim will access an attribute 'name' of 'object' and return the value
    stored there. If the attribute doesn't exist, the default value will be
    returned if present.
    """
    NO_DEFAULT = _dill.Sentinel('_shims.GetAttrShim.NO_DEFAULT')
    def __new__(cls, object, name, default=NO_DEFAULT):
        return Shim.__new__(cls, is_callable=callable(default))
    def __init__(self, object, name, default=NO_DEFAULT):
        if object is None:
            # Use the calling function's module
            object = sys.modules[inspect.currentframe().f_back.f_globals['__name__']]

        if default is GetAttrShim.NO_DEFAULT:
            reduction = (getattr, (object, name))
        else:
            reduction = (getattr, (object, name, default))

        super(GetAttrShim, self).__init__(reduction)

        self.object = object
        self.name = name
        self.default = default
    @classmethod
    def _callable(cls, object, name, default=NO_DEFAULT):
        return callable(default)

def _assign_to_dill_module(func):
    _dill.__dict__[func.__name__] = func
    return func

######################
## Compatibility Shims are defined below
######################

# Used to stay compatible with versions of dill whose _create_cell functions
# do not have a default value.
# Can be safely replaced removed entirely (replaced by empty tuples for calls to
# _create_cell) once breaking changes are allowed.
if _dill.HAS_CTYPES and not _dill.PY3:
    _dill._CELL_EMPTY = _dill.Sentinel('_CELL_EMPTY')
_CELL_EMPTY = GetAttrShim(_dill, '_CELL_EMPTY', None)
_dill._CELL_REF = None


if _dill.OLD37:
    if _dill.HAS_CTYPES and hasattr(_dill.ctypes, 'pythonapi') and hasattr(_dill.ctypes.pythonapi, 'PyCell_Set'):
        # CPython
        ctypes = _dill.ctypes

        _PyCell_Set = ctypes.pythonapi.PyCell_Set

        @_assign_to_dill_module
        def _setattr(object, name, value):
            if type(object) is _dill.CellType and name == 'cell_contents':
                _PyCell_Set.argtypes = (ctypes.py_object, ctypes.py_object)
                _PyCell_Set(object, value)
            else:
                setattr(object, name, value)

        @_assign_to_dill_module
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
        exec('''@_assign_to_dill_module
        def _setattr(cell, name, value):
            if type(cell) is _dill.CellType and name == 'cell_contents':
                def cell_setter(value):
                    %s
                    cell = value # pylint: disable=unused-variable
                func = _dill.FunctionType(cell_setter.__code__, globals(), "", None, (cell,)) # same as cell_setter, but with cell being the cell's contents
                func(value)
            else:
                setattr(cell, name, value)''' % __nonlocal)

        exec('''@_assign_to_dill_module
        def _delattr(cell, name):
            if type(cell) is _dill.CellType and name == 'cell_contents':
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
        from . import _nonlocals
        @_assign_to_dill_module
        @_nonlocals.export_nonlocals('cellv')
        def _setattr(cell, name, value):
            if type(cell) is _dill.CellType and name == 'cell_contents':
                cellv = None
                @_nonlocals.nonlocals('cellv', closure_override=(cell,))
                def cell_setter(value):
                    cellv = value # pylint: disable=unused-variable
                cell_setter(value)
            else:
                setattr(cell, name, value)

        @_assign_to_dill_module
        def _delattr(cell, name):
            if type(cell) is _dill.CellType and name == 'cell_contents':
                pass
            else:
                delattr(cell, name)


_setattr = GetAttrShim(_dill, '_setattr', setattr)
_delattr = GetAttrShim(_dill, '_delattr', delattr)
