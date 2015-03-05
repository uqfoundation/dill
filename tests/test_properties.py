#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2015 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill


class Foo(object):
    def __init__(self):
        self._data = 1

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, x):
        self._data = x

FooS = dill.copy(Foo)

assert FooS.data.fget is not None
assert FooS.data.fset is not None
assert FooS.data.fdel is None

try:
    res = FooS().data
except Exception as e:
    raise AssertionError(str(e))
else:
    assert res == 1

try:
    f = FooS()
    f.data = 1024
    res = f.data
except Exception as e:
    raise AssertionError(str(e))
else:
    assert res == 1024
