#!/usr/bin/env python
#
# Author: Anthony Mercer (@antonsoo)
# Copyright (c) 2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
pickling of itertools objects in CPython 3.14 and later

Python 3.14 removed the ``__reduce__`` and ``__setstate__`` methods of the
itertools types. Here their state is read with ctypes, following the structs
in CPython's Modules/itertoolsmodule.c. An object is rebuilt with its public
constructor, and the fields that a constructor cannot set are then written.

A struct is used only if its size is the ``__basicsize__`` of the type, so an
object with an unknown layout fails to pickle, as before, instead of being
read wrongly. The pickled state does not depend on the layout.
"""

import ctypes
import itertools
from ctypes import POINTER, c_int, c_long, c_ssize_t, c_void_p
from pickle import PicklingError

from ._dill import register
from .logger import adapter as logger

__all__ = []

_incref = ctypes.PYFUNCTYPE(None, ctypes.py_object)(('Py_IncRef', ctypes.pythonapi))
_decref = ctypes.PYFUNCTYPE(None, ctypes.py_object)(('Py_DecRef', ctypes.pythonapi))

_O = c_void_p # a PyObject * field
_LINKCELLS = 57 # the values held by each _tee_dataobject

def _struct(*fields):
    head = [('ob_base', ctypes.c_byte * object.__basicsize__)]
    return type('_Layout', (ctypes.Structure,), {'_fields_': head + list(fields)})

_combinations = _struct(('pool', _O), ('indices', POINTER(c_ssize_t)), ('result', _O),
                        ('r', c_ssize_t), ('stopped', c_int))

# the struct of each type, or of each layout a type has had
_LAYOUTS = {
    itertools.accumulate: [_struct(('total', _O), ('it', _O), ('binop', _O),
                                   ('initial', _O), ('state', c_void_p))],
    itertools.chain: [_struct(('source', _O), ('active', _O))],
    itertools.combinations: [_combinations],
    itertools.combinations_with_replacement: [_combinations],
    itertools.compress: [_struct(('data', _O), ('selectors', _O))],
    itertools.count: [_struct(('cnt', c_ssize_t), ('long_cnt', _O), ('long_step', _O))],
    itertools.cycle: [ # with firstpass up to 3.14.6, without it from 3.14.7
        _struct(('it', _O), ('saved', _O), ('index', c_ssize_t), ('firstpass', c_int)),
        _struct(('it', _O), ('saved', _O), ('index', c_ssize_t))],
    itertools.dropwhile: [_struct(('func', _O), ('it', _O), ('start', c_long))],
    itertools.filterfalse: [_struct(('func', _O), ('it', _O))],
    itertools.groupby: [_struct(('it', _O), ('keyfunc', _O), ('tgtkey', _O), ('currkey', _O),
                                ('currvalue', _O), ('currgrouper', c_void_p),
                                ('state', c_void_p))],
    itertools._grouper: [_struct(('parent', _O), ('tgtkey', _O))],
    itertools.islice: [_struct(('it', _O), ('next', c_ssize_t), ('stop', c_ssize_t),
                               ('step', c_ssize_t), ('cnt', c_ssize_t))],
    itertools.permutations: [_struct(('pool', _O), ('indices', POINTER(c_ssize_t)),
                                     ('cycles', POINTER(c_ssize_t)), ('result', _O),
                                     ('r', c_ssize_t), ('stopped', c_int))],
    itertools.product: [_struct(('pools', _O), ('indices', POINTER(c_ssize_t)),
                                ('result', _O), ('stopped', c_int))],
    itertools.repeat: [_struct(('element', _O), ('cnt', c_ssize_t))],
    itertools.starmap: [_struct(('func', _O), ('it', _O))],
    itertools.takewhile: [_struct(('func', _O), ('it', _O), ('stop', c_long))],
    itertools._tee: [_struct(('dataobj', _O), ('index', c_int), ('weakreflist', _O),
                             ('state', c_void_p))],
    itertools._tee_dataobject: [_struct(('it', _O), ('numread', c_int), ('running', c_int),
                                        ('nextlink', _O), ('values', _O * _LINKCELLS))],
    itertools.zip_longest: [_struct(('tuplesize', c_ssize_t), ('numactive', c_ssize_t),
                                    ('ittuple', _O), ('result', _O), ('fillvalue', _O))],
}

def _view(obj):
    """the struct of an itertools object, read and written in place"""
    size = type(obj).__basicsize__
    for layout in _LAYOUTS.get(type(obj), ()):
        if ctypes.sizeof(layout) == size:
            return layout.from_address(id(obj))
    raise PicklingError("Can't pickle %r: unknown layout of %s" % (obj, type(obj).__qualname__))

def _object(address):
    """the object at a non-NULL address"""
    return ctypes.cast(address, ctypes.py_object).value

def _get(view, name):
    """the object that a field refers to, or None if it is NULL"""
    address = getattr(view, name)
    return _object(address) if address else None

def _opt(view, name):
    """(the object that a field refers to,), or () if it is NULL"""
    address = getattr(view, name)
    return (_object(address),) if address else ()

def _put(view, name, obj):
    """store a new reference to obj in a field, and release the old one"""
    old = getattr(view, name)
    _incref(obj)
    setattr(view, name, id(obj))
    if old:
        _decref(_object(old))

def _save(pickler, obj, func, args):
    logger.trace(pickler, "It: %s", obj)
    pickler.save_reduce(func, args, obj=obj)
    logger.trace(pickler, "# It")


@register(itertools.count)
def save_count(pickler, obj):
    view = _view(obj)
    start = _get(view, 'long_cnt') if view.long_cnt else view.cnt
    _save(pickler, obj, itertools.count, (start, _get(view, 'long_step')))

@register(itertools.repeat)
def save_repeat(pickler, obj):
    view = _view(obj)
    element = _get(view, 'element')
    _save(pickler, obj, itertools.repeat, (element,) if view.cnt < 0 else (element, view.cnt))

@register(itertools.compress)
def save_compress(pickler, obj):
    view = _view(obj)
    _save(pickler, obj, itertools.compress, (_get(view, 'data'), _get(view, 'selectors')))

@register(itertools.filterfalse)
@register(itertools.starmap)
def save_function_iterator(pickler, obj):
    view = _view(obj)
    _save(pickler, obj, type(obj), (_get(view, 'func'), _get(view, 'it')))


def _create_dropwhile(func, it, start):
    obj = itertools.dropwhile(func, it)
    _view(obj).start = start
    return obj

def _create_takewhile(func, it, stop):
    obj = itertools.takewhile(func, it)
    _view(obj).stop = stop
    return obj

@register(itertools.dropwhile)
def save_dropwhile(pickler, obj):
    view = _view(obj)
    _save(pickler, obj, _create_dropwhile, (_get(view, 'func'), _get(view, 'it'), view.start))

@register(itertools.takewhile)
def save_takewhile(pickler, obj):
    view = _view(obj)
    _save(pickler, obj, _create_takewhile, (_get(view, 'func'), _get(view, 'it'), view.stop))


def _create_islice(it, start, stop, step, cnt):
    obj = itertools.islice(it, start, stop, step)
    _view(obj).cnt = cnt
    return obj

@register(itertools.islice)
def save_islice(pickler, obj):
    view = _view(obj)
    if not view.it: # exhausted
        _save(pickler, obj, itertools.islice, (iter(()), 0))
        return
    stop = None if view.stop == -1 else view.stop
    _save(pickler, obj, _create_islice, (_get(view, 'it'), view.next, stop, view.step, view.cnt))


def _create_cycle(it, saved, index):
    """a cycle that reads it while index is negative, then repeats saved from index"""
    obj = itertools.cycle(() if it is None else it)
    view = _view(obj)
    _get(view, 'saved').extend(saved)
    if index >= 0:
        view.index = index
    return obj

@register(itertools.cycle)
def save_cycle(pickler, obj):
    view = _view(obj)
    if hasattr(view, 'firstpass'): # the first pass lasts while it is set
        first = bool(view.it)
    else: # index is negative during the first pass
        first = view.index < 0
    it = _get(view, 'it') if first else None
    _save(pickler, obj, _create_cycle, (it, _get(view, 'saved'), -1 if first else view.index))


def _create_chain(source, *active):
    obj = itertools.chain.from_iterable(source)
    if active:
        _put(_view(obj), 'active', active[0])
    return obj

@register(itertools.chain)
def save_chain(pickler, obj):
    view = _view(obj)
    if not view.source: # exhausted
        _save(pickler, obj, itertools.chain, ())
        return
    _save(pickler, obj, _create_chain, (_get(view, 'source'),) + _opt(view, 'active'))


def _create_accumulate(it, func, initial, *total):
    obj = itertools.accumulate(it, func, initial=initial)
    if total:
        _put(_view(obj), 'total', total[0])
    return obj

@register(itertools.accumulate)
def save_accumulate(pickler, obj):
    view = _view(obj)
    args = (_get(view, 'it'), _get(view, 'binop'), _get(view, 'initial'))
    _save(pickler, obj, _create_accumulate, args + _opt(view, 'total'))


# The combinatoric iterators keep indices into their pools and the result
# tuple last returned. state is None before the first result, True once they
# are exhausted, or else the indices from which the result tuple is rebuilt.

def _create_product(pools, state=None):
    obj = itertools.product(*pools)
    view = _view(obj)
    if state is True:
        view.stopped = 1
    elif state is not None:
        for i, index in enumerate(state):
            view.indices[i] = index
        _put(view, 'result', tuple(pool[index] for pool, index in zip(pools, state)))
    return obj

@register(itertools.product)
def save_product(pickler, obj):
    view = _view(obj)
    pools = _get(view, 'pools')
    if view.stopped:
        args = ((), True)
    elif view.result:
        args = (pools, tuple(view.indices[i] for i in range(len(pools))))
    else:
        args = (pools,)
    _save(pickler, obj, _create_product, args)

def _create_combinations(kind, pool, r, state=None):
    obj = kind(pool, r)
    view = _view(obj)
    if state is True:
        view.stopped = 1
    elif state is not None:
        for i, index in enumerate(state):
            view.indices[i] = index
        _put(view, 'result', tuple(pool[index] for index in state))
    return obj

@register(itertools.combinations)
@register(itertools.combinations_with_replacement)
def save_combinations(pickler, obj):
    view = _view(obj)
    kind, pool, r = type(obj), _get(view, 'pool'), view.r
    if view.stopped:
        args = (kind, (), r, True)
    elif view.result:
        args = (kind, pool, r, tuple(view.indices[i] for i in range(r)))
    else:
        args = (kind, pool, r)
    _save(pickler, obj, _create_combinations, args)

def _create_permutations(pool, r, state=None):
    obj = itertools.permutations(pool, r)
    view = _view(obj)
    if state is True:
        view.stopped = 1
    elif state is not None:
        indices, cycles = state
        for i, index in enumerate(indices):
            view.indices[i] = index
        for i, cycle in enumerate(cycles):
            view.cycles[i] = cycle
        _put(view, 'result', tuple(pool[index] for index in indices[:r]))
    return obj

@register(itertools.permutations)
def save_permutations(pickler, obj):
    view = _view(obj)
    pool, r = _get(view, 'pool'), view.r
    if view.stopped:
        args = ((), r, True)
    elif view.result:
        indices = tuple(view.indices[i] for i in range(len(pool)))
        args = (pool, r, (indices, tuple(view.cycles[i] for i in range(r))))
    else:
        args = (pool, r)
    _save(pickler, obj, _create_permutations, args)


def _create_zip_longest(iterables, fillvalue):
    return itertools.zip_longest(*iterables, fillvalue=fillvalue)

@register(itertools.zip_longest)
def save_zip_longest(pickler, obj):
    view = _view(obj)
    if view.numactive: # an exhausted iterator is set to NULL; it is replaced by ()
        start = view.ittuple + tuple.__basicsize__
        addresses = [c_void_p.from_address(start + i * tuple.__itemsize__).value
                     for i in range(view.tuplesize)]
        iterables = tuple(_object(a) if a else () for a in addresses)
    else: # exhausted
        iterables = ((),) * view.tuplesize
    _save(pickler, obj, _create_zip_longest, (iterables, _get(view, 'fillvalue')))


def _create_groupby(it, keyfunc, tgtkey, currkey, currvalue):
    obj = itertools.groupby(it, keyfunc)
    view = _view(obj)
    for name, value in (('tgtkey', tgtkey), ('currkey', currkey), ('currvalue', currvalue)):
        if value:
            _put(view, name, value[0])
    return obj

@register(itertools.groupby)
def save_groupby(pickler, obj):
    view = _view(obj)
    args = (_get(view, 'it'), _get(view, 'keyfunc'), _opt(view, 'tgtkey'),
            _opt(view, 'currkey'), _opt(view, 'currvalue'))
    _save(pickler, obj, _create_groupby, args)

@register(itertools._grouper)
def save_grouper(pickler, obj):
    view = _view(obj)
    parent = _get(view, 'parent')
    if _view(parent).currgrouper != id(obj): # the groupby has moved on
        _save(pickler, obj, iter, ((),))
        return
    _save(pickler, obj, itertools._grouper, (parent, _get(view, 'tgtkey')))


def _create_tee(dataobj, index):
    obj = itertools._tee(())
    view = _view(obj)
    _put(view, 'dataobj', dataobj)
    view.index = index
    return obj

@register(itertools._tee)
def save_tee(pickler, obj):
    view = _view(obj)
    _save(pickler, obj, _create_tee, (_get(view, 'dataobj'), view.index))

@register(itertools._tee_dataobject)
def save_tee_dataobject(pickler, obj):
    view = _view(obj)
    values = [_object(view.values[i]) for i in range(view.numread)]
    it = _get(view, 'it')
    args = (iter(()) if it is None else it, values, _get(view, 'nextlink'))
    _save(pickler, obj, itertools._tee_dataobject, args)
