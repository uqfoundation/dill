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

The functions :func:`dump_module`, :func:`load_module` and
:func:`load_module_asdict` are capable of saving and restoring, as long as
objects are pickleable, the complete state of a module.  For imported modules
that are pickled, `dill` requires them to be importable at unpickling.

Options like ``dill.settings['byref']`` and ``dill.settings['recurse']`` don't
affect the behavior of :func:`dump_module`.  However, if a module has variables
refering to objects from other modules that would prevent it from pickling or
drastically increase its disk size, using the option ``refimported`` forces them
to be saved by reference instead of by value.

Also with :func:`dump_module`, namespace filters may be used to restrict the
list of pickled variables to a subset of those in the module, based on their
names and values.

In turn, :func:`load_module_asdict` allows one to load the variables from
different saved states of the same module into dictionaries.

Using :func:`dill.detect.trace` enables the complete pickling trace of a
module.  Alternatively, ``dill.detect.trace('INFO')`` enables only the messages
about variables excluded by filtering or unpickleable variables saved by
reference in the pickled module's namespace.

Note:
    Contrary of using :func:`dill.dump` and :func:`dill.load` to save and load
    a module object, :func:`dill.dump_module` always tries to pickle the module
    by value (including built-in modules).  Modules saved with :func:`dill.dump`
    can't be loaded with :func:`dill.load_module`.
"""

from __future__ import annotations

__all__ = [
    'dump_module', 'load_module', 'load_module_asdict', 'is_pickled_module',
    'ModuleFilters', 'NamedObject', 'FilterRules', 'FilterSet', 'size_filter',
    'ipython_filter',
    'dump_session', 'load_session' # backward compatibility
]

import re
import sys
import warnings

from dill import _dill, logging
from dill import Pickler, Unpickler, UnpicklingError
from ._dill import (
    BuiltinMethodType, FunctionType, MethodType, ModuleType, TypeType,
    _getopt, _import_module, _is_builtin_module, _is_imported_module,
    _lookup_module, _main_module, _module_map, _reverse_typemap, __builtin__,
)
from ._utils import FilterRules, FilterSet, _open, size_filter, EXCLUDE, INCLUDE

logger = logging.getLogger(__name__)

# Type hints.
from typing import Any, Dict, Iterable, Optional, Union
from ._utils import Filter, FilterFunction, NamedObject, Rule, RuleType

import pathlib
import tempfile

TEMPDIR = pathlib.PurePath(tempfile.gettempdir())

# Unique objects (with no duplicates) that may be imported with "import as".
IMPORTED_AS_TYPES = (ModuleType, TypeType, FunctionType, MethodType, BuiltinMethodType)
if 'PyCapsuleType' in _reverse_typemap:
    IMPORTED_AS_TYPES += (_reverse_typemap['PyCapsuleType'],)

# For unique objects of various types that have a '__module__' attribute.
IMPORTED_AS_MODULES = [re.compile(x) for x in (
    'ctypes', 'typing', 'subprocess', 'threading',
    r'concurrent\.futures(\.\w+)?', r'multiprocessing(\.\w+)?'
)]

BUILTIN_CONSTANTS = (None, False, True, NotImplemented)

def _stash_modules(main_module):
    """pop imported variables to be saved by reference in the __dill_imported* attributes"""
    modmap = _module_map(main_module)
    newmod = ModuleType(main_module.__name__)
    original = {}
    imported = []
    imported_as = []
    imported_top_level = []  # keep separated for backward compatibility

    for name, obj in main_module.__dict__.items():
        # Avoid incorrectly matching a singleton value in another package (e.g. __doc__ == None).
        if (any(obj is constant for constant in BUILTIN_CONSTANTS)  # must compare by identity
                or type(obj) is str and obj == ''  # for cases like: __package__ == ''
                or type(obj) is int and -128 <= obj <= 256  # small values or CPython-internalized
                or isinstance(obj, ModuleType) and _is_builtin_module(obj)  # always saved by ref
                or obj is main_module or obj is main_module.__dict__):
            original[name] = obj
        else:
            modname = getattr(obj, '__module__', None)
            lookup_by_id = (
                isinstance(obj, IMPORTED_AS_TYPES)
                or modname is not None
                    and any(regex.fullmatch(modname) for regex in IMPORTED_AS_MODULES)
            )
            source_module, objname, _ = _lookup_module(modmap, name, obj, lookup_by_id)
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
        _discard_added_variables(newmod, main_module.__dict__)
        return newmod, modmap
    else:
        return main_module, modmap

def _restore_modules(unpickler, main_module):
    for modname, name in main_module.__dict__.pop('__dill_imported', ()):
        main_module.__dict__[name] = unpickler.find_class(modname, name)
    for modname, objname, name in main_module.__dict__.pop('__dill_imported_as', ()):
        main_module.__dict__[name] = unpickler.find_class(modname, objname)
    for modname, name in main_module.__dict__.pop('__dill_imported_top_level', ()):
        main_module.__dict__[name] = _import_module(modname)

def _filter_vars(main_module, exclude, include, base_rules):
    """apply exclude/include filters from arguments *and* settings"""
    rules = FilterRules()
    mod_rules = base_rules.get_rules(main_module.__name__)
    rules.exclude |= mod_rules.get_filters(EXCLUDE)
    rules.include |= mod_rules.get_filters(INCLUDE)
    if exclude is not None:
        rules.update([(EXCLUDE, exclude)])
    if include is not None:
        rules.update([(INCLUDE, include)])

    namespace = rules.apply_filters(main_module.__dict__)
    if namespace is main_module.__dict__:
        return main_module

    if logger.isEnabledFor(logging.INFO):
        excluded = {name: type(value).__name__
                for name, value in sorted(main_module.__dict__.items()) if name not in namespace}
        excluded = str(excluded).translate({ord(","): "\n  ", ord("'"): None})
        logger.info("[dump_module] Variables excluded by filtering:\n  %s", excluded)

    newmod = ModuleType(main_module.__name__)
    newmod.__dict__.update(namespace)
    _discard_added_variables(newmod, namespace)
    return newmod

def _discard_added_variables(main, original_namespace):
    # Some empty attributes like __doc__ may have been added by ModuleType().
    added_names = set(main.__dict__)
    added_names.discard('__name__')  # required
    added_names.difference_update(original_namespace)
    added_names.difference_update('__dill_imported%s' % s for s in ('', '_as', '_top_level'))
    for name in added_names:
        delattr(main, name)

def _fix_module_namespace(main, original_main):
    # Self-references.
    for name, obj in main.__dict__.items():
        if obj is original_main:
            setattr(main, name, main)
        elif obj is original_main.__dict__:
            setattr(main, name, main.__dict__)
    # Trick _is_imported_module(), forcing main to be saved as an imported module.
    if getattr(main, '__loader__', None) is None and _is_imported_module(original_main):
        main.__loader__ = True  # will be discarded by _dill.save_module()

def dump_module(
    filename = str(TEMPDIR/'session.pkl'),
    module: Optional[Union[ModuleType, str]] = None,
    *,
    refimported: Optional[bool] = None,
    refonfail: Optional[bool] = None,
    exclude: Optional[Union[Filter, Iterable[Filter]]] = None,
    include: Optional[Union[Filter, Iterable[Filter]]] = None,
    base_rules: Optional[ModuleFilters] = None,
    **kwds
) -> None:
    """Pickle the current state of :mod:`__main__` or another module to a file.

    Save the contents of :mod:`__main__` (e.g. from an interactive
    interpreter session), an imported module, or a module-type object (e.g.
    built with :class:`~types.ModuleType`), to a file. The pickled
    module can then be restored with the function :func:`load_module`.

    Only a subset of the module's variables may be saved if exclusion/inclusion
    filters are specified.  Filters are applied to every pair of variable's name
    and value to determine if they should be saved or not.  They can be set in
    ``dill.session.settings['filters']`` or passed directly to the ``exclude``
    and ``include`` parameters.

    See :class:`FilterRules` and :class:`ModuleFilters` for details. See
    also the bundled "filter factories": :class:`size_filter` and
    :func:`ipython_filter`.

    Parameters:
        filename: a path-like object or a writable stream.
        module: a module object or the name of an importable module. If `None`
            (the default), :mod:`__main__` is saved.
        refimported: if `True`, all objects identified as having been imported
            into the module's namespace are saved by reference. *Note:* this is
            similar but independent from ``dill.settings['byref']``, as
            ``refimported`` refers to virtually all imported objects, while
            ``byref`` only affects select objects.
        refonfail: if `True` (the default), objects that fail to pickle by value
            will try to be saved by reference.  If this also fails, saving their
            parent objects by reference will be attempted recursively.  In the
            worst case scenario, the module itself may be saved by reference,
            with a warning.  *Note:* this has the side effect of disabling framing
            for pickle protocol ≥ 4.  Turning this option off may improve
            unpickling speed, but may cause a module to fail pickling.
        exclude: one or more variable `exclusion` filters (see
            :class:`FilterRules`).
        include: one or more variable `inclusion` filters.
        base_rules: if passed, overwrites ``settings['filters']``.
        **kwds: extra keyword arguments passed to :class:`Pickler()`.

    Raises:
        :exc:`PicklingError`: if pickling fails.
        :exc:`PicklingWarning`: if the module itself ends being saved by
            reference due to unpickleable objects in its namespace.

    Default values for keyword-only arguments can be set in
    `dill.session.settings`.

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
          >>> dill.dump_module('foo_session.pkl', module=foo)

        - Save the state of a module with unpickleable objects:

          >>> import dill
          >>> import os
          >>> os.altsep = '\\'
          >>> dill.dump_module('os_session.pkl', module=os, refonfail=False)
          PicklingError: ...
          >>> dill.dump_module('os_session.pkl', module=os, refonfail=True) # the default

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
          p\\a\\t\\h

        - Use `refimported` to save imported objects by reference:

          >>> import dill
          >>> from html.entities import html5
          >>> type(html5), len(html5)
          (dict, 2231)
          >>> import io
          >>> buf = io.BytesIO()
          >>> dill.dump_module(buf) # saves __main__, with html5 saved by value
          >>> len(buf.getvalue()) # pickle size in bytes
          71665
          >>> buf = io.BytesIO()
          >>> dill.dump_module(buf, refimported=True) # html5 saved by reference
          >>> len(buf.getvalue())
          438

        - Save current session but exclude some variables:

          >>> import dill
          >>> num, text, alist = 1, 'apple', [4, 9, 16]
          >>> dill.dump_module(exclude=['text', int])) # only 'alist' is saved

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

    from .settings import settings as dill_settings
    protocol = dill_settings['protocol']
    refimported = _getopt(settings, 'refimported', refimported)
    refonfail = _getopt(settings, 'refonfail', refonfail)
    base_rules = _getopt(settings, 'filters', base_rules)
    if not isinstance(base_rules, ModuleFilters): #pragma: no cover
        base_rules = ModuleFilters(base_rules)

    main = module
    if main is None:
        main = _main_module
    elif isinstance(main, str):
        main = _import_module(main)
    if not isinstance(main, ModuleType):
        raise TypeError("%r is not a module" % main)
    original_main = main
    main = _filter_vars(main, exclude, include, base_rules)
    if refimported:
        main, modmap = _stash_modules(original_main)
    with _open(filename, 'wb', seekable=True) as file:
        pickler = Pickler(file, protocol, **kwds)
        pickler._main = main     #FIXME: dill.settings are disabled
        pickler._byref = False   # disable pickling by name reference
        pickler._recurse = False # disable pickling recursion for globals
        pickler._session = True  # is best indicator of when pickling a session
        pickler._first_pass = True
        if main is not original_main:
            pickler._original_main = original_main
            _fix_module_namespace(main, original_main)
        if refonfail:
            pickler._refonfail = True  # False by default
            pickler._file_seek = file.seek
            pickler._file_truncate = file.truncate
            pickler._saved_byref = []
            if refimported:
                # Cache modmap for refonfail.
                pickler._modmap = modmap
        if logger.isEnabledFor(logging.TRACE):
            pickler._id_to_name = {id(v): k for k, v in main.__dict__.items()}
        pickler.dump(main)
    if pickler._saved_byref and logger.isEnabledFor(logging.INFO):
        import textwrap
        pickler._saved_byref.sort()
        message = "[dump_module] Variables saved by reference (refonfail): "
        message += str(pickler._saved_byref).replace("'", "")[1:-1]
        logger.info("\n".join(textwrap.wrap(message, width=80)))
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
    try:
        opcodes = ((opcode.name, arg) for opcode, arg, pos in pickletools.genops(file.peek(256))
                   if opcode.name not in NEUTRAL)
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
        # ValueError also occours when the end of the chunk is reached (without a STOP).
        if isinstance(error, NotImplementedError) and main is not None:
            # The file is not peekable, but we have the argument main.
            return None
        raise UnpicklingError("unable to identify module") from error

def is_pickled_module(
    filename, importable: bool = True, identify: bool = False
) -> Union[bool, str]:
    """Check if a file can be loaded with :func:`load_module`.

    Check if the file is a pickle file generated with :func:`dump_module`,
    and thus can be loaded with :func:`load_module`.

    Parameters:
        filename: a path-like object or a readable stream.
        importable: expected kind of the file's saved module. Use `True` for
            importable modules (the default) or `False` for module-type objects.
        identify: if `True`, return the module name if the test succeeds.

    Returns:
        `True` if the pickle file at ``filename`` was generated with
        :func:`dump_module` **AND** the module whose state is saved in it is
        of the kind specified by the ``importable`` argument. `False` otherwise.
        If `identify` is set, return the name of the module instead of `True`.

    Examples:
        Create three types of pickle files:

        >>> import dill
        >>> import types
        >>> dill.dump_module('module_session.pkl') # saves __main__
        >>> dill.dump_module('module_object.pkl', module=types.ModuleType('example'))
        >>> with open('common_object.pkl', 'wb') as file:
        >>>     dill.dump('example', file)

        Test each file's kind:

        >>> dill.is_pickled_module('module_session.pkl') # the module is importable
        True
        >>> dill.is_pickled_module('module_session.pkl', importable=False)
        False
        >>> dill.is_pickled_module('module_object.pkl') # the module is not importable
        False
        >>> dill.is_pickled_module('module_object.pkl', importable=False)
        True
        >>> dill.is_pickled_module('module_object.pkl', importable=False, identify=True)
        'example'
        >>> dill.is_pickled_module('common_object.pkl') # always return False
        False
        >>> dill.is_pickled_module('common_object.pkl', importable=False)
        False
    """
    with _open(filename, 'rb', peekable=True) as file:
        try:
            pickle_main = _identify_module(file)
        except UnpicklingError:
            return False
    is_runtime_mod = pickle_main.startswith('__runtime__.')
    res = importable ^ is_runtime_mod
    if res and identify:
        return pickle_main.partition('.')[-1] if is_runtime_mod else pickle_main
    else:
        return res

def load_module(
    filename = str(TEMPDIR/'session.pkl'),
    module: Optional[Union[ModuleType, str]] = None,
    **kwds
) -> Optional[ModuleType]:
    """Update the selected module with the state saved at ``filename``.

    Restore a module to the state saved with :func:`dump_module`. The
    saved module can be :mod:`__main__` (e.g. an interpreter session),
    an imported module, or a module-type object (e.g. created with
    :class:`~types.ModuleType`).

    When restoring the state of a non-importable, module-type object, the
    current instance of this module may be passed as the argument ``module``.
    Otherwise, a new instance is created with :class:`~types.ModuleType`
    and returned.

    Parameters:
        filename: a path-like object or a readable stream.
        module: a module object or the name of an importable module;
            the module's name and kind (i.e. imported or non-imported) must
            match the name and kind of the module stored at ``filename``.
        **kwds: extra keyword arguments passed to :class:`Unpickler()`.

    Raises:
        :exc:`UnpicklingError`: if unpickling fails.
        :exc:`ValueError`: if the argument ``module`` and the module
            saved at ``filename`` are incompatible.

    Returns:
        A module object, if the saved module is not :mod:`__main__` and
        a module instance wasn't provided with the argument ``module``.

    Passing an argument to ``module`` forces `dill` to verify that the module
    being loaded is compatible with the argument value.  Additionally, if the
    argument is a module instance (instead of a module name), it supresses the
    return value. Each case and behavior is exemplified below:

        1. `module`: ``None`` --- This call loads a previously saved state of
        the module ``math`` and returns it (the module object) at the end:

            >>> import dill
            >>> # load module -> restore state -> return module
            >>> dill.load_module('math_session.pkl')
            <module 'math' (built-in)>

        2. `module`: ``str`` --- Passing the module name does the same as above,
        but also verifies that the module being loaded, restored and returned is
        indeed ``math``:

            >>> import dill
            >>> # load module -> check name/kind -> restore state -> return module
            >>> dill.load_module('math_session.pkl', module='math')
            <module 'math' (built-in)>
            >>> dill.load_module('math_session.pkl', module='cmath')
            ValueError: can't update module 'cmath' with the saved state of module 'math'

        3. `module`: ``ModuleType`` --- Passing the module itself instead of its
        name has the additional effect of suppressing the return value (and the
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
        # Resolve main.
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

        # Check against the pickle's main.
        is_main_imported = _is_imported_module(main)
        if pickle_main is not None:
            is_runtime_mod = pickle_main.startswith('__runtime__.')
            if is_runtime_mod:
                pickle_main = pickle_main.partition('.')[-1]
            error_msg = "can't update{} module{} %r with the saved state of{} module{} %r"
            if main.__name__ != pickle_main:
                raise ValueError(error_msg.format("", "", "", "") % (main.__name__, pickle_main))
            elif is_runtime_mod and is_main_imported:
                raise ValueError(
                    error_msg.format(" imported", "", "", "-type object")
                    % (main.__name__, main.__name__)
                )
            elif not is_runtime_mod and not is_main_imported:
                raise ValueError(
                    error_msg.format("", "-type object", " imported", "")
                    % (main.__name__, main.__name__)
                )

        # Load the module's state.
        #FIXME: dill.settings are disabled
        unpickler = Unpickler(file, **kwds)
        unpickler._session = True
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
    **kwds
) -> Dict[str, Any]:
    """
    Load the contents of a saved module into a dictionary.

    ``load_module_asdict()`` is the near-equivalent of::

        lambda filename: vars(dill.load_module(filename)).copy()

    however, it does not alter the original module. Also, the path of
    the loaded file is stored with the key ``'__session__'``.

    Parameters:
        filename: a path-like object or a readable stream
        **kwds: extra keyword arguments passed to :class:`Unpickler()`

    Raises:
        :exc:`UnpicklingError`: if unpickling fails

    Returns:
        A copy of the restored module's dictionary.

    Note:
        Even if not changed, the module refered in the file is always loaded
        before its saved state is restored from `filename` to the dictionary.

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
        >>> new_var in main # it was initialized with the current state of __main__
        True
    """
    if 'module' in kwds:
        raise TypeError("'module' is an invalid keyword argument for load_module_asdict()")

    with _open(filename, 'rb', peekable=True) as file:
        main_qualname = _identify_module(file)
        main = _import_module(main_qualname)
        main_copy = ModuleType(main_qualname)
        main_copy.__dict__.clear()
        main_copy.__dict__.update(main.__dict__)

        parent_name, _, main_name = main_qualname.rpartition('.')
        if parent_name:
            parent = sys.modules[parent_name]
        try:
            sys.modules[main_qualname] = main_copy
            if parent_name and getattr(parent, main_name, None) is main:
                setattr(parent, main_name, main_copy)
            load_module(file, **kwds)
        finally:
            sys.modules[main_qualname] = main
            if parent_name and getattr(parent, main_name, None) is main_copy:
                setattr(parent, main_name, main)

    if isinstance(getattr(filename, 'name', None), str):
        main_copy.__session__ = filename.name
    else:
        main_copy.__session__ = str(filename)
    return main_copy.__dict__

class ModuleFilters(FilterRules):
    """Stores default filtering rules for modules.

    :class:`FilterRules` subclass with a tree-like structure that may hold
    exclusion/inclusion filters for specific modules and submodules.  See the
    base class documentation to learn more about how to create and use filters.

    This is the type of ``dill.session.settings['filters']``:

    >>> import dill
    >>> filters = dill.session.settings['filters']
    >>> filters
    <ModuleFilters DEFAULT: exclude=FilterSet(), include=FilterSet()>

    Exclusion and inclusion filters for global variables can be added using the
    ``add()`` methods of the ``exclude`` and ``include`` attributes, or of the
    ``ModuleFilters`` object itself.  In the latter case, the filter is added to
    its ``exclude`` :class:`FilterSet` by default:

    >>> filters.add('some_var') # exclude a variable named 'some_var'
    >>> filters.exclude.add('_.*') # exclude any variable with a name prefixed by '_'
    >>> filters.include.add('_keep_this') # an exception to the rule above
    >>> filters
    <ModuleFilters DEFAULT:
      exclude=FilterSet(names={'some_var'}, regexes={re.compile('_.*')}),
      include=FilterSet(names={'_keep_this'})>

    Similarly, a filter can be discarded with the ``discard()`` method:

    >>> filters.discard('some_var')
    >>> filters.exclude.discard('_.*')
    >>> filters
    <ModuleFilters DEFAULT: exclude=FilterSet(), include=FilterSet(names={'_keep_this'})>

    Note how, after the last operation, ``filters.exclude`` was left empty but
    ``filters.include`` still contains a name filter.  In cases like this, i.e.
    when ``len(filters.exclude) == 0 and len(filters.include) > 0.``, the
    filters are treated as an "allowlist", which means that **only** the
    variables that match the ``include`` filters will be pickled.  In this
    example, only the variable ``_keep_this``, if it existed, would be saved.

    To create filters specific for a module and its submodules, use the
    following syntax to add a child node to the default ``ModuleFilters``:

    >>> import dill
    >>> from dill.session import EXCLUDE, INCLUDE
    >>> filters = dill.session.settings['filters']
    >>> # set empty rules for module 'foo':
    >>> # (these will override any existing default rules)
    >>> filters['foo'] = []
    >>> filters['foo']
    <ModuleFilters for 'foo': exclude=FilterSet(), include=FilterSet()>
    >>> # add a name (exclusion) filter:
    >>> # (this filter will also apply to any submodule of 'foo')
    >>> filters['foo'].add('ignore_this')
    >>> filters['foo']
    <ModuleFilters for 'foo': exclude=FilterSet(names={'ignore_this'}), include=FilterSet()>

    Create a filter for a submodule:

    >>> filters['bar.baz'] = [
    ...     (EXCLUDE, r'\w+\d+'),
    ...     (INCLUDE, ['ERROR403', 'ERROR404'])
    ... ]
    >>> # set specific rules for the submodule 'bar.baz':
    >>> filters['bar.baz']
    <ModuleFilters for 'bar.baz':
      exclude=FilterSet(regexes={re.compile('\\w+\\d+')}),
      include=FilterSet(names={'ERROR403', 'ERROR404'})>
    >>> # note that the default rules still apply to the module 'bar'
    >>> filters['bar']
    <ModuleFilters for 'bar': NOT SET>

    Module-specific filter rules may be accessed using different syntaxes:

    >>> filters['bar.baz'] is filters['bar']['baz']
    True
    >>> filters.bar.baz is filters['bar']['baz']
    True

    Note, however, that using the attribute syntax to directly set rules for
    a submodule will fail if its parent module doesn't have an entry yet:

    >>> filters.parent.child = [] # filters.parent doesn't exist
    AttributeError: 'ModuleFilters' object has no attribute 'parent'
    >>> filters['parent.child'] = [] # use this syntax instead
    >>> filters.parent.child.grandchild = [(EXCLUDE, str)] # works fine
    """
    __slots__ = '_module', '_parent', '__dict__'

    def __init__(self,
        rules: Union[Iterable[Rule], FilterRules, None] = None,
        module: str = 'DEFAULT',
        parent: ModuleFilters = None,
    ):
        if rules is not None:
            super().__init__(rules)
        # else: don't initialize FilterSets.
        if parent is not None and parent._module != 'DEFAULT':
            module = '%s.%s' % (parent._module, module)
        # Bypass self.__setattr__()
        super().__setattr__('_module', module)
        super().__setattr__('_parent', parent)

    def __repr__(self) -> str:
        desc = "DEFAULT" if self._module == 'DEFAULT' else "for %r" % self._module
        return "<ModuleFilters %s:%s" % (desc, super().__repr__().partition(':')[-1])
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ModuleFilters):
            return super().__eq__(other) and self._module == other._module
        elif isinstance(other, FilterRules):
            return super().__eq__(other)
        else:
            return NotImplemented

    def __setattr__(self, name: str, value: Any) -> None:
        if name in FilterRules.__slots__:
            # Don't interfere with superclass attributes.
            super().__setattr__(name, value)
        elif name in ('exclude', 'include'):
            if not (hasattr(self, 'exclude') or hasattr(self, 'include')):
                # This was a placeholder node. Initialize 'other'.
                other = 'include' if name == 'exclude' else 'exclude'
                super().__setattr__(other, ())
            super().__setattr__(name, value)
        else:
            # Create a child node for submodule 'name'.
            mod_filters = ModuleFilters(rules=value, module=name, parent=self)
            super().__setattr__(name, mod_filters)
    # Proxy __setitem__ and __getitem__ to self.__dict__ through attributes.
    def __setitem__(self, name: str, value: Union[Iterable[Rule], FilterRules, None]) -> None:
        if '.' not in name:
            setattr(self, name, value)
        else:
            module, _, submodules = name.partition('.')
            if module not in self.__dict__:
                # Create a placeholder node, like logging.PlaceHolder.
                setattr(self, module, None)
            mod_filters = getattr(self, module)
            mod_filters[submodules] = value
    def __getitem__(self, name: str) -> ModuleFilters:
        module, _, submodules = name.partition('.')
        mod_filters = getattr(self, module)
        if not submodules:
            return mod_filters
        else:
            return mod_filters[submodules]

    def keys(self) -> List[str]:
        values = self.__dict__.values()
        # Don't include placeholder nodes.
        keys = [x._module for x in values if hasattr(x, 'exclude') or hasattr(x, 'include')]
        for mod_filters in values:
            keys += mod_filters.keys()
        keys.sort()
        return keys
    def get_rules(self, name: str) -> ModuleFilters:
        while name:
            try:
                return self[name]
            except AttributeError:
                name = name.rpartition('.')[0]
        return self
    def get_filters(self, rule_type: RuleType) -> FilterSet:
        """Get exclude/include filters. If not set, fall back to parent module's or default filters."""
        if not isinstance(rule_type, RuleType):
            raise ValueError("invalid rule type: %r (must be one of %r)" % (rule_type, list(RuleType)))
        try:
            return getattr(self, rule_type.name.lower())
        except AttributeError:
            if self._parent is None:
                raise
            return self._parent.get_filters(rule_type)


## Session settings ##

settings = {
    'refimported': False,
    'refonfail': True,
    'filters': ModuleFilters(rules=()),
}


## Session filter factories ##

def ipython_filter(*, keep_history: str = 'input') -> FilterFunction:
    """Filter factory to exclude IPython hidden variables.

    When saving the session with :func:`dump_module` from an IPython
    interpreter, hidden variables (i.e. variables listed by ``dir()`` but
    not listed by the ``%who`` magic command) are saved unless they are excluded
    by filters.  This function generates a filter that will exclude these hidden
    variables from the list of saved variables, with the optional exception of
    command history variables.

    Parameters:
        keep_history: whether to keep (i.e. not exclude) the input and output
          history of the IPython interactive session. Accepted values:

            - `"input"`: the input history contained in the hidden variables
              ``In``, ``_ih``, ``_i``, ``_i1``, ``_i2``, etc. will be saved.
            - `"output"`, the output history contained in the hidden variables
              ``Out``, ``_oh``, ``_``, ``_1``, ``_2``, etc. will be saved.
            - `"both"`: both the input and output history will be saved.
            - `"none"`: all the hidden history variables will be excluded.

    Returns:
        A variable exclusion filter function to be used with :func:`dump_module`.

    Important:
        A filter of this kind should be created just before the call to
        :func:`dump_module` where it's used, as it doesn't update the list of
        hidden variables after its creation for performance reasons.

    Example:

        >>> import dill
        >>> from dill.session import ipython_filter
        >>> dill.dump_module(exclude=ipython_filter(keep_history='none'))
    """
    HISTORY_OPTIONS = {'input', 'output', 'both', 'none'}
    if keep_history not in HISTORY_OPTIONS: #pramga: no cover
        raise ValueError(
            "invalid 'keep_history' argument: %r (must be one of %r)" %
            (keep_history, HISTORY_OPTIONS)
        )
    if not _dill.IS_IPYTHON: #pragma: no cover
        # Return no-op filter if not in IPython.
        return (lambda x: False)

    from IPython import get_ipython
    ipython_shell = get_ipython()

    # Code snippet adapted from IPython.core.magics.namespace.who_ls()
    user_ns = ipython_shell.user_ns
    user_ns_hidden = ipython_shell.user_ns_hidden
    NONMATCHING = object()  # This can never be in user_ns
    interactive_vars = {x for x in user_ns if user_ns[x] is not user_ns_hidden.get(x, NONMATCHING)}

    # Input and output history hidden variables.
    history_regex = []
    if keep_history in {'input', 'both'}:
        interactive_vars |= {'_ih', 'In', '_i', '_ii', '_iii'}
        history_regex.append(re.compile(r'_i\d+'))
    if keep_history in {'output', 'both'}:
        interactive_vars |= {'_oh', 'Out', '_', '__', '___'}
        history_regex.append(re.compile(r'_\d+'))

    def not_interactive_var(obj: NamedObject) -> bool:
        if any(regex.fullmatch(obj.name) for regex in history_regex):
            return False
        return obj.name not in interactive_vars

    return not_interactive_var


## Variables set in this module to avoid circular import problems ##

# Internal exports for backward compatibility with dill v0.3.5.1
for name in (
    '_restore_modules', '_stash_modules',
    'dump_session', 'load_session' # backward compatibility functions
):
    setattr(_dill, name, globals()[name])

del name
