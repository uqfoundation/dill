#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2021 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
Provides shims for compatibility between versions of dill and Python.
"""

import inspect, sys

_dill = sys.modules['dill._dill']

# The values for the shims for this particular version of dill and Python.
_dill_true_values = {}

class Shim(object):
    """
    A wrapper object that refers to a shim object in the module if it exists and
    to another object if it doesn't exist. This choice is made during the
    unpickle step instead of the pickling process.
    """
    def __new__(cls, name, alternative, module=None):
        if callable(alternative):
            return object.__new__(_CallableShim)
        else:
            return object.__new__(cls)
    def __init__(self, name, alternative, module=None):
        if _dill_true_values is not None:
            self.module = _dill
            g = globals()
            if name in g:
                _dill_true_values[name] = g[name]
        elif module is None:
            # Use the calling function's module
            self.module = sys.modules[inspect.currentframe().f_back.f_globals['__name__']]
        else:
            self.module = module
        self.name = name
        self.alternative = alternative
    def __copy__(self):
        return self # pragma: no cover
    def __deepcopy__(self, memo):
        return self # pragma: no cover
    def __reduce__(self):
        return (getattr, (self.module, self.name, self.alternative))
    def __reduce_ex__(self, protocol):
        return self.__reduce__()

class _CallableShim(Shim):
    def __call__(self, *args, **kwargs):
        return getattr(self.module, self.name, self.alternative)(*args, **kwargs) # pragma: no cover

# Used to stay compatible with versions of dill whose _create_cell functions
# do not have a default value.
# Can be safely replaced removed entirely (replaced by empty tuples for calls to
# _create_cell) once breaking changes are allowed.
_CELL_EMPTY = _dill.Sentinel('_CELL_EMPTY')
_CELL_EMPTY = Shim('_CELL_EMPTY', None)
_dill_true_values['_CELL_REF'] = None


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

        def _delattr(cell, name):
            if type(cell) is _dill.CellType and name == 'cell_contents':
                pass
            else:
                delattr(cell, name)


_setattr = Shim('_setattr', setattr)
_delattr = Shim('_delattr', delattr)

# Update dill._dill with shim functions
sys.modules['dill._dill'].__dict__.update(_dill_true_values)
_dill_true_values = None
