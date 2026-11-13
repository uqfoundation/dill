#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import dill
import enum
import sys

# test enum classes defined in a module dill cannot import them from
# (the interactive `__main__` case of issues #250 and #697)
class Color(enum.Enum):
    RED = 1
    GREEN = 2

class Priority(enum.IntEnum):
    LOW = 0
    HIGH = 10
    def double(self):
        return self._value_ * 2

class Permissions(enum.Flag):
    R = 1
    W = 2

class AutoNumbered(enum.Enum):
    A = enum.auto()
    B = enum.auto()

class Aliased(enum.Enum):
    A = 1
    B = 1

class Empty(enum.Enum):
    pass

class Documented(enum.Enum):
    """some documentation"""
    X = 1

class Shaped(int, enum.Enum):
    M = 5

class CustomNew(enum.Enum):
    A = 'a'
    def __new__(cls, value):
        obj = object.__new__(cls)
        obj._value_ = value.upper()
        return obj

class MultiArg(enum.Enum):
    P = (1, 2)
    def __new__(cls, x, y):
        obj = object.__new__(cls)
        obj._value_ = (x, y)
        obj.xy = x * y
        return obj

def test_enum_classes():
    _Color = dill.loads(dill.dumps(Color))
    assert [m.name for m in _Color] == ['RED', 'GREEN']
    assert _Color.RED._value_ == 1
    assert _Color(2) is _Color.GREEN

    _Priority = dill.loads(dill.dumps(Priority))
    assert [m.name for m in _Priority] == ['LOW', 'HIGH']
    assert _Priority.HIGH.double() == 20
    assert isinstance(_Priority.HIGH, int)

    _Permissions = dill.loads(dill.dumps(Permissions))
    assert (_Permissions.R | _Permissions.W).value == 3

    _AutoNumbered = dill.loads(dill.dumps(AutoNumbered))
    assert [m._value_ for m in _AutoNumbered] == [1, 2]

    _Aliased = dill.loads(dill.dumps(Aliased))
    assert [m.name for m in _Aliased] == ['A']
    assert _Aliased.B is _Aliased.A

    _Empty = dill.loads(dill.dumps(Empty))
    assert list(_Empty) == []

    _Documented = dill.loads(dill.dumps(Documented))
    assert _Documented.__doc__ == 'some documentation'

    _Shaped = dill.loads(dill.dumps(Shaped))
    assert _Shaped.M._value_ == 5
    assert isinstance(_Shaped.M, int)

    _CustomNew = dill.loads(dill.dumps(CustomNew))
    assert [m.name for m in _CustomNew] == ['A']
    assert _CustomNew.A._value_ == 'A'

    _MultiArg = dill.loads(dill.dumps(MultiArg))
    assert _MultiArg.P._value_ == (1, 2)
    assert _MultiArg.P.xy == 2

def test_enum_members():
    member = dill.loads(dill.dumps(Color.RED))
    assert member._name_ == 'RED'
    assert member._value_ == 1
    assert member is member.__class__.RED

def test_functional_enum():
    # enums built through the functional API, pickled by value
    def make_enum():
        return enum.Enum('MadeUp', 'ONE TWO')
    made = make_enum()
    _made = dill.loads(dill.dumps(made))
    assert [m.name for m in _made] == ['ONE', 'TWO']
    assert _made.TWO._value_ == 2

def test_str_enum():
    if sys.version_info < (3, 11):
        return
    class Text(enum.StrEnum):
        A = 'a'
        B = 'b'
    _Text = dill.loads(dill.dumps(Text))
    assert [m._value_ for m in _Text] == ['a', 'b']
    assert str(_Text.A) == 'a'

if __name__ == '__main__':
    test_enum_classes()
    test_enum_members()
    test_functional_enum()
    test_str_enum()
    # when this module is `__main__`, the classes above live in the
    # interactive session: round-tripped members reconcile to the
    # live members (issues #250 and #697)
    assert dill.copy(Color.RED) is Color.RED
    assert dill.copy(Priority.LOW) is Priority.LOW
    print('Success')
