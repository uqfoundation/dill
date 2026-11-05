#!/usr/bin/env python
#
# Author: Anthony Mercer (@antonsoo)
# Copyright (c) 2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
test pickling itertools objects at each stage of their iteration
"""

import ctypes
import itertools
import operator
import sys
import warnings

import dill
from dill._dill import IS_PYPY

# python 3.12 and 3.13 warn that itertools objects will stop being picklable
warnings.filterwarnings('ignore', category=DeprecationWarning)

steps = 12

def check(make, expand=list):
    """copies made after each number of steps continue as the original does"""
    for k in range(steps + 1):
        obj = make()
        for _ in itertools.islice(obj, k):
            pass
        copy = dill.copy(obj)
        assert type(copy) is type(obj)
        assert expand(itertools.islice(copy, 3 * steps)) == \
               expand(itertools.islice(obj, 3 * steps)), (make(), k)

cases = [
    lambda: itertools.count(),
    lambda: itertools.count(5, 2),
    lambda: itertools.count(1.5, 0.25),
    lambda: itertools.count(2**70, -3),
    lambda: itertools.repeat('x'),
    lambda: itertools.repeat('x', 5),
    lambda: itertools.cycle('abc'),
    lambda: itertools.cycle(''),
    lambda: itertools.cycle(iter([1, 2, 3, 4, 5])),
    lambda: itertools.chain('ab', '', 'cde'),
    lambda: itertools.chain.from_iterable([[1], [], [2, 3], [4]]),
    lambda: itertools.islice(range(100), 3, 40, 4),
    lambda: itertools.islice(itertools.count(), 5),
    lambda: itertools.islice('abcdefgh', 2, None),
    lambda: itertools.accumulate([1, 2, 3, 4, 5]),
    lambda: itertools.accumulate([1, 2, 3, 4], operator.mul),
    lambda: itertools.accumulate([1, 2, 3], initial=10),
    lambda: itertools.accumulate([]),
    lambda: itertools.product('ab', range(3)),
    lambda: itertools.product('ab', repeat=3),
    lambda: itertools.product(),
    lambda: itertools.product('ab', ''),
    lambda: itertools.combinations('abcde', 3),
    lambda: itertools.combinations('ab', 3),
    lambda: itertools.combinations_with_replacement('abc', 2),
    lambda: itertools.combinations_with_replacement('', 2),
    lambda: itertools.permutations('ab', 3),
    lambda: itertools.compress('abcdef', [1, 0, 1, 0, 1, 1]),
    lambda: itertools.filterfalse(None, [0, 1, 0, 2, 3, 0]),
    lambda: itertools.filterfalse(lambda x: x % 2, range(10)),
    lambda: itertools.starmap(pow, [(2, 5), (3, 2), (10, 3)]),
    lambda: itertools.dropwhile(lambda x: x < 5, [1, 4, 6, 4, 1]),
    lambda: itertools.takewhile(lambda x: x < 5, [1, 4, 6, 4, 1]),
    lambda: itertools.zip_longest('abc', 'defgh', '', fillvalue='-'),
    lambda: itertools.zip_longest(),
]

# Before 3.14, and in pypy, python pickles itertools objects itself, and gets
# these wrong: pypy permutations and tee, and in cpython a count that reaches
# sys.maxsize, and a combinations of r=0 once exhausted.
if not IS_PYPY:
    cases += [
        lambda: itertools.permutations('abcd', 2),
        lambda: itertools.permutations('abc'),
        lambda: itertools.tee('abcdefgh')[1],
    ]
if not IS_PYPY and sys.hexversion >= 0x30e00a1:
    cases += [
        lambda: itertools.count(sys.maxsize - 3), # crosses into arbitrary precision
        lambda: itertools.combinations('', 0),
    ]

def test_iterators():
    for make in cases:
        check(make)

def groups(groupby):
    return [(key, list(group)) for key, group in groupby]

def test_groupby():
    check(lambda: itertools.groupby('aaabbbccd'), groups)
    check(lambda: itertools.groupby('aAabBc', str.lower), groups)
    data = 'aaabbbccd'
    for taken in range(4):
        parent = itertools.groupby(data)
        key, group = next(parent)
        for _ in itertools.islice(group, taken):
            pass
        # a copy of the groupby skips the rest of the current group
        assert groups(dill.copy(parent)) == groups(dill.copy(parent))
        copy, group_copy = dill.copy((parent, group))
        assert list(group_copy) == list(group)
        assert groups(copy) == groups(parent)
    parent = itertools.groupby(data)
    _, old = next(parent)
    next(parent)
    assert list(dill.copy(old)) == [] # the groupby has moved past it

def test_tee():
    if IS_PYPY: # pypy pickles tee objects itself, and loses their position
        return
    a, b = itertools.tee(iter(range(150))) # more values than one link holds
    for _ in range(70):
        next(a)
    for _ in range(10):
        next(b)
    a2, b2 = dill.copy((a, b))
    assert list(a2) == list(range(70, 150))
    assert list(b2) == list(range(10, 150))
    assert list(dill.copy(b)) == list(range(10, 150))
    assert list(a) == list(range(70, 150))

def test_unknown_layout():
    if IS_PYPY or sys.hexversion < 0x30e00a1:
        return
    from dill import _itertools
    layouts = _itertools._LAYOUTS[itertools.count]
    # a struct that is not the size of the type is not used
    _itertools._LAYOUTS[itertools.count] = [_itertools._struct(('cnt', ctypes.c_ssize_t))]
    try:
        dill.dumps(itertools.count())
    except dill.PicklingError:
        pass
    else:
        raise AssertionError('pickled with the wrong layout')
    finally:
        _itertools._LAYOUTS[itertools.count] = layouts

def test_shared_iterator():
    it = iter(range(10))
    head, rest = dill.copy((itertools.islice(it, 3), it))
    assert list(head) == [0, 1, 2]
    assert list(rest) == list(range(3, 10))

if __name__ == '__main__':
    test_iterators()
    test_groupby()
    test_tee()
    test_unknown_layout()
    test_shared_iterator()
