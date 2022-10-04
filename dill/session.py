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
that are pickled, `dill` assumes that they are importable when unpickling.

Contrary of using :func:`dill.dump` and :func:`dill.load` to save and load a
module object, :func:`dill.dump_module` always tries to pickle the module by
value (including built-in modules).  Also, options like
``dill.settings['byref']`` and ``dill.settings['recurse']`` don't affect its
behavior.

However, if a module contains references to objects originating from other
modules, that would prevent it from pickling or drastically increase its disk
size, they can be saved by reference instead of by value, using the option
``refimported``.
"""

__all__ = [
    'dump_module', 'load_module', 'load_module_asdict',
    'dump_session', 'load_session' # backward compatibility
]

import re
import sys
import warnings

from dill import _dill, logging
from dill import Pickler, Unpickler, UnpicklingError
from ._dill import (
    BuiltinMethodType, FunctionType, MethodType, ModuleType, TypeType,
    _import_module, _is_builtin_module, _is_imported_module,
    _lookup_module, _main_module, _module_map, _reverse_typemap, __builtin__,
)
from ._utils import _open

logger = logging.getLogger(__name__)

# Type hints.
from typing import Any, Dict, Optional, Union

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

def _stash_modules(main_module, original_main):
    """pop imported variables to be saved by reference in the __dill_imported* attributes"""
    modmap = _module_map(original_main)
    newmod = ModuleType(main_module.__name__)
    original = {}
    imported = []
    imported_as = []
    imported_top_level = []  # keep separated for backward compatibility

    for name, obj in main_module.__dict__.items():
        # Avoid incorrectly matching a singleton value in another package (e.g. __doc__ == None).
        if (any(obj is constant for constant in BUILTIN_CONSTANTS)  # must compare by identity
                or type(obj) is str and obj == ''  # internalized, for cases like: __package__ == ''
                or type(obj) is int and -128 <= obj <= 256  # possibly cached by compiler/interpreter
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

        if logger.isEnabledFor(logging.INFO):
            refimported = [(name, "%s.%s" % (mod, name)) for mod, name in imported]
            refimported += [(name, "%s.%s" % (mod, objname)) for mod, objname, name in imported_as]
            refimported += [(name, mod) for mod, name in imported_top_level]
            message = "[dump_module] Variables saved by reference (refimported):\n"
            logger.info(message + _format_log_dict(dict(refimported)))
        logger.debug("main namespace after _stash_modules(): %s", dir(newmod))

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

def _format_log_dict(dict):
    return pprint.pformat(dict, compact=True, sort_dicts=True).replace("'", "")

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
    **kwds
) -> None:
    """Pickle the current state of :mod:`__main__` or another module to a file.

    Save the contents of :mod:`__main__` (e.g. from an interactive
    interpreter session), an imported module, or a module-type object (e.g.
    built with :class:`~types.ModuleType`), to a file. The pickled
    module can then be restored with the function :func:`load_module`.

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

    *Changed in version 0.3.6:* Function ``dump_session()`` was renamed to
    ``dump_module()``.  Parameters ``main`` and ``byref`` were renamed to
    ``module`` and ``refimported``, respectively.

    Note:
        Currently, ``dill.settings['byref']`` and ``dill.settings['recurse']``
        don't apply to this function.`
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
    if refimported is None: refimported = settings['refimported']
    if refonfail is None: refonfail = settings['refonfail']

    main = module
    if main is None:
        main = _main_module
    elif isinstance(main, str):
        main = _import_module(main)
    if not isinstance(main, ModuleType):
        raise TypeError("%r is not a module" % main)
    original_main = main

    logger.debug("original main namespace: %s", dir(main))
    if refimported:
        main, modmap = _stash_modules(main, original_main)

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
    if refonfail and pickler._saved_byref and logger.isEnabledFor(logging.INFO):
        saved_byref = {var: "%s.%s" % (mod, obj) for var, mod, obj in pickler._saved_byref}
        message = "[dump_module] Variables saved by reference (refonfail):\n"
        logger.info(message + _format_log_dict(saved_byref))
    return

# Backward compatibility.
def dump_session(filename=str(TEMPDIR/'session.pkl'), main=None, byref=False, **kwds):
    warnings.warn("dump_session() has been renamed dump_module()", PendingDeprecationWarning)
    dump_module(filename, module=main, refimported=byref, **kwds)
dump_session.__doc__ = dump_module.__doc__

def _identify_module(file, main=None):
    """identify the name of the module stored in the given file-type object"""
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


## Session settings ##

settings = {
    'refimported': False,
    'refonfail': True,
}


## Variables set in this module to avoid circular import problems ##

# Internal exports for backward compatibility with dill v0.3.5.1
for name in (
    '_restore_modules', '_stash_modules',
    'dump_session', 'load_session' # backward compatibility functions
):
    setattr(_dill, name, globals()[name])
del name
