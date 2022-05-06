#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2019-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import functools
import dill
import sys
dill.settings['recurse'] = True


def is_py3():
    return hex(sys.hexversion) >= '0x30000f0'


def function_a(a):
    return a


def function_b(b, b1):
    return b + b1


def function_c(c, c1=1):
    return c + c1


def function_d(d, d1, d2=1):
    """doc string"""
    return d + d1 + d2

function_d.__module__ = 'a module'


if is_py3():
    exec('''
def function_e(e, *e1, e2=1, e3=2):
    return e + sum(e1) + e2 + e3''')

    globalvar = 0

    @functools.lru_cache(None)
    def function_with_cache(x):
        global globalvar
        globalvar += x
        return globalvar


def function_with_unassigned_variable():
    if False:
        value = None
    return (lambda: value)


def test_functions():
    dumped_func_a = dill.dumps(function_a)
    assert dill.loads(dumped_func_a)(0) == 0

    dumped_func_b = dill.dumps(function_b)
    assert dill.loads(dumped_func_b)(1,2) == 3

    dumped_func_c = dill.dumps(function_c)
    assert dill.loads(dumped_func_c)(1) == 2
    assert dill.loads(dumped_func_c)(1, 2) == 3

    dumped_func_d = dill.dumps(function_d)
    assert dill.loads(dumped_func_d).__doc__ == function_d.__doc__
    assert dill.loads(dumped_func_d).__module__ == function_d.__module__
    assert dill.loads(dumped_func_d)(1, 2) == 4
    assert dill.loads(dumped_func_d)(1, 2, 3) == 6
    assert dill.loads(dumped_func_d)(1, 2, d2=3) == 6

    if is_py3():
        function_with_cache(1)
        globalvar = 0
        dumped_func_cache = dill.dumps(function_with_cache)
        assert function_with_cache(2) == 3
        assert function_with_cache(1) == 1
        assert function_with_cache(3) == 6
        assert function_with_cache(2) == 3

    empty_cell = function_with_unassigned_variable()
    cell_copy = dill.loads(dill.dumps(empty_cell))
    assert 'empty' in str(cell_copy.__closure__[0])
    try:
        cell_copy()
    except:
        # this is good
        pass
    else:
        raise AssertionError('cell_copy() did not read an empty cell')

    if is_py3():
        exec('''
dumped_func_e = dill.dumps(function_e)
assert dill.loads(dumped_func_e)(1, 2) == 6
assert dill.loads(dumped_func_e)(1, 2, 3) == 9
assert dill.loads(dumped_func_e)(1, 2, e2=3) == 8
assert dill.loads(dumped_func_e)(1, 2, e2=3, e3=4) == 10
assert dill.loads(dumped_func_e)(1, 2, 3, e2=4) == 12
assert dill.loads(dumped_func_e)(1, 2, 3, e2=4, e3=5) == 15''')

if __name__ == '__main__':
    test_functions()
