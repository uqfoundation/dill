#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import sys

import dill
dill.settings['recurse'] = True


class Foo(object):
    def __init__(self):
        self._data = 1

    def _get_data(self):
        return self._data

    def _set_data(self, x):
        self._data = x

    data = property(_get_data, _set_data)


def test_data_not_none():
    FooS = dill.copy(Foo)
    assert FooS.data.fget is not None
    assert FooS.data.fset is not None
    assert FooS.data.fdel is None


def test_data_unchanged():
    FooS = dill.copy(Foo)
    try:
        res = FooS().data
    except Exception:
        e = sys.exc_info()[1]
        raise AssertionError(str(e))
    else:
        assert res == 1


def test_data_changed():
    FooS = dill.copy(Foo)
    try:
        f = FooS()
        f.data = 1024
        res = f.data
    except Exception:
        e = sys.exc_info()[1]
        raise AssertionError(str(e))
    else:
        assert res == 1024
