#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill

# test classdefs
class _class:
    def _method(self):
        pass
    def ok(self):
        return True

class _class2:
    def __call__(self):
        pass
    def ok(self):
        return True

class _newclass(object):
    def _method(self):
        pass
    def ok(self):
        return True

class _newclass2(object):
    def __call__(self):
        pass
    def ok(self):
        return True

o = _class()
oc = _class2()
n = _newclass()
nc = _newclass2()

clslist = [_class,_class2,_newclass,_newclass2]
objlist = [o,oc,n,nc]
_clslist = [dill.dumps(obj) for obj in clslist]
_objlist = [dill.dumps(obj) for obj in objlist]

for obj in clslist:
    globals().pop(obj.__name__)
del clslist
for obj in ['o','oc','n','nc']:
    globals().pop(obj)
del objlist
del obj

for obj,cls in zip(_objlist,_clslist):
    _cls = dill.loads(cls)
    _obj = dill.loads(obj)
    assert _obj.ok()
    assert _cls.ok(_cls())

# test namedtuple
import sys
if hex(sys.hexversion) >= '0x20600f0':
    from collections import namedtuple

    Z = namedtuple("Z", ['a','b'])
    Zi = Z(0,1)
    X = namedtuple("Y", ['a','b'])
    X.__name__ = "X" #XXX: name must 'match' or fails to pickle
    Xi = X(0,1)

    assert Z == dill.loads(dill.dumps(Z))
    assert Zi == dill.loads(dill.dumps(Zi))
    assert X == dill.loads(dill.dumps(X))
    assert Xi == dill.loads(dill.dumps(Xi))

try:
    import numpy as np

    class TestArray(np.ndarray):
        def __new__(cls, input_array, color):
            obj = np.asarray(input_array).view(cls)
            obj.color = color 
            return obj
        def __array_finalize__(self, obj):
            if obj is None:
                return
            if isinstance(obj, type(self)):
                self.color = obj.color
        def __getnewargs__(self):
            return np.asarray(self), self.color

    a1 = TestArray(np.zeros(100), color='green')
    assert dill.pickles(a1)
    assert a1.__dict__ == dill.copy(a1).__dict__

    a2 = a1[0:9]
    assert dill.pickles(a2)
    assert a2.__dict__ == dill.copy(a2).__dict__

    class TestArray2(np.ndarray):
        color = 'blue'

    a3 = TestArray2([1,2,3,4,5])
    a3.color = 'green'
    assert dill.pickles(a3)
    assert a3.__dict__ == dill.copy(a3).__dict__

except ImportError: pass


# EOF
