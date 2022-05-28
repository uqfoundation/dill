#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
Implementation of the bootstrap header for dill "portable" mode
"""
__all__ = ['bootstrap_header']

import builtins, dill, io, logging, pickletools
from dill import _dill
from functools import partial
from pickle import _Pickler as PyPickler
from pickle import BUILD, DICT, GLOBAL, MARK, POP, PROTO, REDUCE, SETITEM, STOP, TUPLE
from ._dill import _code_args, _create_code, _create_typemap, _import_module

# Referenced in the bootstrap header.
import collections, importlib, inspect, operator, pickle, re, types, zlib

logger = logging.getLogger('dill._bootstrap')

# Common kwargs for code.replace() from Py3.8 to Py3.11.
COMMON_CODE_MEMBERS = (
    'co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_nlocals',
    'co_stacksize', 'co_flags', 'co_firstlineno', 'co_code', 'co_consts', 'co_names',
    'co_varnames', 'co_freevars', 'co_cellvars', 'co_filename', 'co_name'
    )

header_cache = {}

def update_revtypemap(revtypemap):
    import functools, importlib, io, operator, types
    revtypemap['PartialType'] = type(functools.partial(int, base=2))
    revtypemap['SuperType'] = type(super(Exception, TypeError()))
    revtypemap['ItemGetterType'] = type(operator.itemgetter(0))
    revtypemap['AttrGetterType'] = type(operator.attrgetter('__repr__'))
    for mod, prefix in [('io', ''), ('_pyio', 'Py')]:
        try:
            mod = importlib.import_module(mod)
            revtypemap[f'{prefix}FileType'] = getattr(mod, 'FileIO')
            revtypemap[f'{prefix}BufferedRandomType'] = getattr(mod, 'BufferedRandom')
            revtypemap[f'{prefix}BufferedReaderType'] = getattr(mod, 'BufferedReader')
            revtypemap[f'{prefix}BufferedWriterType'] = getattr(mod, 'BufferedWriter')
            revtypemap[f'{prefix}TextWrapperType'] = getattr(mod, 'TextIOWrapper')
        except (ModuleNotFoundError, AttributeError):
            pass
    try:
        revtypemap['ExitType'] = type(exit) if not exit.__module__.startswith('IPython') else None
    except NameError:
        pass
    try:
        from ctypes import pythonapi
    except ImportError:  # PyPy
        revtypemap['WrapperDescriptorType'] = types.MethodType
        revtypemap['MethodDescriptorType'] = types.FunctionType
        revtypemap['ClassMethodDescriptorType'] = types.FunctionType
    return revtypemap

def write_proto(buffer, protocol):
    from struct import pack
    if protocol >= 2:
        buffer.write(PROTO + pack("<B", protocol))

def write_global(buffer, module, attr):
    buffer.write(b'%c%b\n%b\n' % (GLOBAL, module.encode('ascii'), attr.encode('ascii')))

class PiecewiseDoc:
    def __init__(self, doc):
        self.data = [doc]
    def __iadd__(self, value):
        self.data.append(value)
        return self
    def __repr__(self):
        return "".join(self.data)
    def clear(self):
        self.data[:] = self.data[:1]
        return self

def bootstrap_header(protocol):
    """
    Generate the dill bootstrap header for the specified protocol

    The header is returned as a bytes object to be directly written to the
    pickle stream, prepended to the pickled object and, therefore:

      - Should leave the Unpickler stack empty after unpickling;
      - Can't use memoization (to be compatible with cPickle in the future);
      - Shouldn't use framming.

    Pseudo-code
    -----------

    >>> dill = ModuleType('dill')
    >>> dill.__version__ = PICKLER_VERSION
    >>> _dill = ModuleType('dill._dill')
    >>> _dill.__builtins__ = builtins
    >>> dill._dill = _dill
    >>> has_dill = find_spec('dill')
    >>> sys.modules['dill'] = import_module('dill') if has_dill else dill
    >>> sys.modules['dill._dill'] = import_module('dill._dill') if has_dill else _dill
    >>> version = getattr(dill, 'version', '')
    >>> bootstrap = not has_dill or version < PICKLER_VERSION
    >>> payload = pickle.loads(PAYLOAD if bootstrap else {})
    >>> vars(_dill).update(payload)

    Equivalent Python code
    ----------------------

    This is directly run by the (un)pickling machine.
    Note: variable assignments are just for clearness.
    """
    doc = bootstrap_header.__doc__.clear()

    header_protocol = min(protocol, 3)  # don't use framing
    try:
        return header_cache[header_protocol]
    except KeyError:
        pass

    # Bootstrap header.
    buf = io.BytesIO()
    write = buf.write
    write_proto(buf, protocol)

    pickler = PyPickler(buf, header_protocol)
    pickler.fast = True  # don't use memo!
    save = partial(pickler.save, save_persistent_id=False)
    save_global = pickler.save_global  # bypass _dill.save_type
    save_reduce = pickler.save_reduce

    def x_if_cond_else_y(cond, x, y):
        write_global(buf, '_globals', 'ifelse')
        write(MARK)

        # Tuple (y, x)
        write(MARK)
        for obj in (y, x):
            if callable(obj) and obj.__module__ == __name__:
                obj()
            else:
                save(obj)
        write(TUPLE)

        # False (0) or True (1)
        save_global(bool)
        write(MARK)
        if callable(cond):
            cond()
        else:
            save(cond)
        write(TUPLE + REDUCE)

        # Get x or y
        write(TUPLE + REDUCE)

    ######################
    #  Bootstrap header  #
    ######################

    doc += """
    Create a bootstrap module to serve as a memo.
    >>> bootstrap_mod = types.ModuleType('_globals', doc='dill bootstrap')
    >>> sys.modules['_globals'] = bootstrap_mod
    >>> _globals.get = vars(_globals).__getitem__
    >>> _globals.ifelse = tuple.__getitem__
    stack: [sys.modules, vars(_globals)]
    """
    write_global(buf, 'sys', 'modules')
    save('_globals')
    write_global(buf, 'types', 'ModuleType')
    save(('_globals', 'dill bootstrap'))
    write(REDUCE + SETITEM)
    write_global(buf, '_globals', '__dict__')
    save('get')
    save(getattr)
    write(MARK)
    write_global(buf, '_globals', '__dict__')
    save('__getitem__')
    write(TUPLE + REDUCE + SETITEM)
    save('ifelse')
    save(getattr)
    write(MARK)
    save_global(tuple)
    save('__getitem__')
    write(TUPLE + REDUCE + SETITEM)

    doc += """
    Bootstrap dill._dill module.
    >>> _dill = types.ModuleType('dill._dill')
    >>> _dill.__builtins__ = importlib.import_module('builtins')
    >>> _dill.PY3 = True
    stack: [sys.modules, vars(_globals)]
    """
    save('dill._dill')
    write_global(buf, 'types', 'ModuleType')
    save(('dill._dill',))
    write(REDUCE + MARK)
    save('__builtins__')
    save_reduce(importlib.import_module, ('builtins',))
    save('PY3')
    save(True)
    write(DICT + BUILD + SETITEM)

    doc += """
    Bootstrap dill module.
    >>> dill_spec = importlib.util.spec_from_loader('dill', loader=None)
    >>> dill = importlib.util.module_from_spec(dill_spec)
    >>> dill._dill = _dill
    >>> dill.__version__ = PICKLER_VERSION
    stack: [sys.modules, vars(_globals)]
    """
    save('dill')
    save(importlib.util.module_from_spec)
    write(MARK)
    save_reduce(importlib.util.spec_from_loader, ('dill', None))
    write(TUPLE + REDUCE + MARK)
    save('_dill')
    write_global(buf, '_globals', 'get')
    save(('dill._dill',))
    write(REDUCE)
    save('__version__')
    save(dill.__version__)
    write(DICT + BUILD + SETITEM)

    doc += """
    Add dill and _dill to sys.modules.
    >>> has_dill = bool(importlib.util.find_spec('dill'))
    >>> get_mod = ifelse((_globals.get, importlib.import_module), has_dill)
    >>> sys.modules['dill'] = get_mod('dill')
    >>> sys.modules['dill._dill'] = get_mod('dill._dill')
    stack: []
    """
    save('has_dill')
    save_global(bool)
    write(MARK)
    save_reduce(importlib.util.find_spec, ('dill',))
    write(TUPLE + REDUCE + SETITEM + POP)  # pop _globals

    for module in ('dill', 'dill._dill'):
        save(module)
        has_dill = lambda: write_global(buf, '_globals', 'has_dill')
        globals_get = lambda: write_global(buf, '_globals', 'get')
        # globals_get._saver = True
        x_if_cond_else_y(cond=has_dill, x=importlib.import_module, y=globals_get)
        save((module,))
        write(REDUCE + SETITEM)  # sys.modules['module'] = module
    write(POP)  # pop sys.modules

    doc += """
    Should we bootstrap the constructors?
    >>> unpickler_version = getattr(dill.info, 'this_version')
    >>> current_dill = operator.le(PICKLER_VERSION, unpickler_version)
    >>> dont_bootstrap = operator.and_(has_dill, current_dill)
    stack: []
    """
    def dont_bootstrap():
        save(operator.and_)
        write(MARK)
        write_global(buf, '_globals', 'has_dill')
        save(operator.le)
        write(MARK)

        def tuple_version():
            save_global(tuple)
            write(MARK)
            save_global(map)
            write(MARK)
            save_global(int)
            save(re.findall)
            write(MARK)
            save(r'(?:^|\.)(\d+)')

        tuple_version()
        save(dill.__version__)
        write(3*(TUPLE + REDUCE))

        tuple_version()
        save(getattr)
        write(MARK)
        save_reduce(importlib.import_module, ('dill',))
        save('__version__')
        save('')
        write(4*(TUPLE + REDUCE))

        write(2*(TUPLE + REDUCE))

    doc += """
    Last, unpickle the payload if we are bootstrapping.
    >>> stream = ifelse((EMPTY_DICT, payload), dont_bootstrap)
    >>> vars(dill._dill).update(pickle.loads(stream))
    stack: []
    """
    payload = zlib.compress(bootstrap_payload(header_protocol))
    def decompress_payload():
        save_reduce(zlib.decompress, (payload,))
    EMPTY = b'N.'

    save(pickle.loads)
    write(MARK)
    x_if_cond_else_y(cond=dont_bootstrap, x=EMPTY, y=decompress_payload)
    write(TUPLE + REDUCE + POP)  # update _dill with the payload and free the stack

    ###################
    #  End of header  #
    ###################

    header = buf.getvalue()
    buf.close()
    header_cache[header_protocol] = header
    return header

bootstrap_header.__doc__ = PiecewiseDoc(bootstrap_header.__doc__)

def bootstrap_payload(protocol):
    """
    CodeType.replace signature

    Version | code.replace() signature
    --------|-------------------------
      3.8   | replace(self, /, *, co_argcount=-1, co_posonlyargcount=-1, co_kwonlyargcount=-1,
      3.11  | replace(self, /, *, co_argcount=-1, co_posonlyargcount=-1, co_kwonlyargcount=-1,
      3.8   |   ...   co_nlocals=-1, co_stacksize=-1, co_flags=-1, co_firstlineno=-1,
      3.11  |   ...   co_nlocals=-1, co_stacksize=-1, co_flags=-1, co_firstlineno=-1,
      3.8   |   ...   co_code=None, co_consts=None, co_names=None, co_varnames=None,
      3.11  |   ...   co_code=None, co_consts=None, co_names=None, co_varnames=None,
      3.8   |   ...   co_freevars=None, co_cellvars=None, co_filename=None, co_name=None,
      3.11  |   ...   co_freevars=None, co_cellvars=None, co_filename=None, co_name=None,
      3.8   |   ...   co_lnotab=None)
      3.11  |   ...   co_qualname=None, co_linetable=None, co_exceptiontable=None)

    def _bootstrap_constructor:
        _bootstrap_code_co = partial(pickler._doc.__code__.replace(**_cc_co_kwargs[:12]))
        _bootstrap_code = types.FunctionType(_bootstrap_code_co, _cc_globals, _cc_name)
        _create_code_co = _bootstrap_code_co(*_cc_co_args)
        _create_code = types.FunctionType(_create_code_co, _cc_globals, _cc_name)
    """
    doc = bootstrap_payload.__doc__.clear()

    buf = io.BytesIO()
    write = buf.write
    write_proto(buf, protocol)

    pickler = PyPickler(buf, protocol)
    save = partial(pickler.save, save_persistent_id=False)
    save_global = pickler.save_global
    save_reduce = pickler.save_reduce
    memoize = pickler.memoize

    ###########################################
    #  Begin of payload (basic constructors)  #
    ###########################################

    # Populate vars(_dill) with objects used by _create_code.
    write_global(buf, 'dill._dill', '__dict__')
    memoize(vars(_dill))
    save('PY3')
    save(True)
    write(SETITEM)
    save('CodeType')
    write_global(buf, 'types', 'CodeType')
    write(SETITEM)
    save('inspect')  # for Sentinel
    save_reduce(importlib.import_module, ('inspect',))
    write(SETITEM)
    save('__builtin__')
    save_reduce(importlib.import_module, ('builtins',), obj=builtins)
    write(SETITEM)
    write(POP)

    write_global(buf, 'dill', '_dill')

    write(MARK)  # open first batch of globals

    save('_create_function')  # dict key
    write_global(buf, 'types', 'FunctionType')
    memoize(types.FunctionType)
    save('_create_code')
    # _create_code is generated from the code below.

    # _create_code bootstrapping pseudocode:
    #   _bootstrap_code__code__ = partial(types.new_class.__code__.replace, **code_kwargs)()
    #   _bootstrap_code = FunctionType(_bootstrap_code__code__, ?)
    #   _create_code__code__ = _bootstrap_code(*code_args)
    #   _create_code = types.FunctionType(_create_code__code__, vars(_dill))
    code_replace = types.new_class.__code__.replace  # could be any simple function

    # Prepare the last calls.
    save(types.FunctionType)
    write(MARK)
    save(types.FunctionType)
    write(MARK)

    # functools.partial + (code_replace,) + REDUCE
    write_global(buf, 'functools', 'partial')
    write(MARK)

    # Get a CodeType.replace bound method.
    save(getattr)
    write(MARK)
    save(getattr)
    save((types.new_class, '__code__'))
    write(REDUCE)  # new_class.__code__
    save('replace')
    write(TUPLE + REDUCE)  # new_class.__code__.replace
    memoize(code_replace)  # fake it as if saved normally

    write(TUPLE + REDUCE)  # partial_code_replace

    # Format expected by partial.__setstate__.
    # partial_code_replace + (code_replace, (), code_kwargs, None) + BUILD
    co_kwargs = {key: getattr(_create_code.__code__, key) for key in COMMON_CODE_MEMBERS}
    pickler.save_global(bytes)  # bypass _dill.save_type for empty bytes objects
    write(POP)  # discard bytes
    save((code_replace, (), co_kwargs, None))
    write(BUILD + MARK + TUPLE + REDUCE)  # _bootstrap_code.__code__
    save(vars(_dill))
    write(TUPLE + REDUCE)  # _bootstrap_code (call FunctionType(code, __globals__))

    # Call "_bootstrap_code".
    save(_code_args(_create_code.__code__))
    write(REDUCE)  # _create_code.__code__

    # Call FunctionType.
    save(vars(_dill))
    write(TUPLE + REDUCE)  # _create_code, finally!
    memoize(_create_code)

    # Save _create_type and _import_module
    for func in ('_create_type', '_import_module'):
        save(func)
        save(types.FunctionType)
        write(MARK)
        save_reduce(_create_code, _code_args(vars(_dill)[func].__code__))
        save(vars(_dill))
        save(func)
        save(vars(_dill)[func].__defaults__)
        write(TUPLE + REDUCE)

    write(DICT + BUILD)  # close first batch of globals

    ##################################
    #  Remainings dill constructors  #
    ##################################

    # Non-builtin things saved as constructors by dill
    #
    # $ awk '/^\s*pickler\.save_reduce/ { sub("[,)]$", "", $1); sub("^pickler\\.save_reduce\\(", "", $1); print $1 }' dill/_dill.py | LC_COLLATE=C sort -u
    # *possible_postproc
    # *reduce_socket(obj)
    # *reduction
    # ClassType
    # DictProxyType
    # MethodType
    # Reduce(*)
    # _create_array
    # _create_cell
    # _create_code
    # _create_dtypemeta
    # _create_filehandle
    # _create_ftype
    # _create_lock
    # _create_namedtuple
    # _create_rlock
    # _create_stringi
    # _create_stringo
    # _create_weakproxy
    # _create_weakref
    # _eval_repr
    # _get_attr
    # _getattr
    # _import_module
    # _load_type
    # _shims._delattr
    # type(obj)
    #
    # $ awk '/^\s*_save_with_postproc/ { sub("\\(pickler,$", "", $1); print $1$2 }' dill/_dill.py
    # _save_with_postproc(_create_function
    # _save_with_postproc(_create_type

    dill_constructors = [
            #'_create_code', '_create_function', '_create_type', '_import_module',  # already saved
            '_create_array', '_create_cell', '_create_dtypemeta', '_create_filehandle',
            '_create_ftype', '_create_lock', '_create_namedtuple', '_create_rlock',
            '_create_stringi', '_create_stringo', '_create_typemap', '_create_weakproxy',
            '_create_weakref', '_eval_repr', '_get_attr', '_getattr', '_load_type',
            #'_shims._delattr',
            ]

    # Get all global variables used by constructors.
    dill_globals = {}
    for func in dill_constructors:
        dill_globals.update(dill.detect.globalvars(vars(_dill)[func], builtin=True))
    for func in dill_constructors:
        if func in dill_globals:
            del dill_globals[func]
    del dill_globals['PY3'], dill_globals['__builtin__']  # already saved
    del dill_globals['_reverse_typemap']  # constructed at the end
    dill_constructors.remove('_create_typemap')

    global_modules = {}
    global_types = {}
    for name, obj in list(dill_globals.items()):
        if isinstance(obj, types.FunctionType) and obj.__module__ == 'dill._dill':
            dill_constructors.append(name)
            del dill_globals[name]
        elif obj is getattr(builtins, name, None):
            del dill_globals[name]
        elif isinstance(obj, types.ModuleType):
            global_modules[name] = dill_globals.pop(name)
        elif isinstance(obj, type):
            global_types[name] = dill_globals.pop(name)

    logger.info("\nObjects saved in the second stage of the payload:")
    logger.info("_dill global modules: %s", list(global_modules))
    logger.info("_dill global types: %s", list(global_types))
    logger.info("_dill global objects: %s", list(dill_globals))
    logger.info("_dill global functions: %s", dill_constructors)

    write(MARK)  # open second batch of globals

    # Save constructors and other referenced functions.
    func_attrs = ('__qualname__', '__module__', '__kwdefaults__', '__doc__', '__annotations__')
    for name in dill_constructors:
        save(name)
        func = vars(_dill)[name]
        save_reduce(
                _dill._create_function,
                (func.__code__, vars(_dill), func.__name__, func.__defaults__, func.__closure__),
                (vars(func), {k: v for k in func_attrs if (v := getattr(func, k, None)) is not None}),
                )

    # Save global objects.
    for name, module in global_modules.items():
        save(name)
        save_reduce(_dill._import_module, (module.__name__, True))

    types_names = {v: k for k, v in vars(types).items() if isinstance(v, type)}
    for name, klass in global_types.items():
        save(name)
        if klass in types_names:
            write_global(buf, 'types', types_names[klass])
        else:
            mod = klass.__module__
            write_global(buf, mod.lstrip('_') if mod != '_thread' else mod, klass.__name__)

    save_global(bool)
    write(POP)
    def has_module(var, module):
        save(var)
        save(bool)
        write(MARK)
        save_reduce(importlib.util.find_spec, ('ctypes',))
        write(TUPLE + REDUCE)
        del dill_globals[var]
    has_module('HAS_CTYPES', 'ctypes')
    has_module('NumpyDType', 'numpy')
    del dill_globals['NumpyArrayType'], dill_globals['NumpyUfuncType']  # not accessed

    save_global(type)  # bypass save_type
    save_global(object)
    write(POP + POP)
    save('Sentinel')
    _dill.Sentinel.__module__ = '__main__'  # trick _locate_function
    save(_dill.Sentinel)
    _dill.Sentinel.__module__ = 'dill._dill'
    # save({'__module__': 'dill._dill'})
    # write(BUILD)
    save('_CELL_EMPTY')
    save_reduce(_dill.Sentinel, ('_CELL_EMPTY',))
    del dill_globals['_CELL_EMPTY']

    for name, value in dill_globals.items():
        save(name)
        save(value)

    # save function for single use
    def single_call(func):
        save(types.FunctionType)
        write(MARK)
        save_reduce(_create_code, _code_args(func.__code__))
        save(vars(_dill))
        write(TUPLE + REDUCE)

    # save update_revtypemap
    save('_reverse_typemap')
    single_call(update_revtypemap)
    write(MARK)
    save_global(dict)
    write(MARK)
    single_call(_create_typemap)
    write(MARK + 3*(TUPLE + REDUCE))

    write(DICT + BUILD + STOP)  # close second batch of globals

    ####################
    #  End of payload  #
    ####################

    payload = buf.getvalue()
    buf.close()
    return pickletools.optimize(payload)

bootstrap_payload.__doc__ = PiecewiseDoc(bootstrap_payload.__doc__)

if __name__ == '__main__':
    import pickle, pprint, sys
    header = bootstrap_header(protocol=3)
    print(bootstrap_header.__doc__)
    if '--header' in sys.argv or '--payload' in sys.argv:
        try:
            pickletools.dis(header)
        except ValueError as error:
            if error.args[0] != 'pickle exhausted before seeing STOP':
                raise

    logger.setLevel(logging.INFO)
    payload = bootstrap_payload(protocol=3)
    print(bootstrap_payload.__doc__, end="")
    if '--payload' in sys.argv:
        # Payload disassemble is really long...
        print()
        pickletools.dis(payload)
    print(f"\nPayload size: {len(payload)} bytes",
          f"Compressed payload size: {len(zlib.compress(payload))} bytes",
          f"Bootstrap header size: {len(header)} bytes",
          sep="\n")
