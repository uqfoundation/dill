#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import abc
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


def test_property_name():
    assert dill.copy(property()).fget is None
    named_abstract = abc.abstractproperty(Foo._get_data)
    named_abstract.__name__ = 'named_abstract'
    properties = [named_abstract]
    if hasattr(Foo.data, '__name__'):
        renamed = property(Foo._get_data)
        renamed.__name__ = 'renamed'
        properties.extend((Foo.data, renamed))
    for original in properties:
        restored = dill.copy(original)
        assert restored.__name__ == original.__name__
        assert restored.fget(Foo()) == 1


if __name__ == '__main__':
    test_data_not_none()
    test_data_unchanged()
    test_data_changed()
    test_property_name()
