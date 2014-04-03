#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill as pickle
#import pickle

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
_clslist = [pickle.dumps(obj) for obj in clslist]
_objlist = [pickle.dumps(obj) for obj in objlist]

for obj in clslist:
    globals().pop(obj.__name__)
del clslist
for obj in ['o','oc','n','nc']:
    globals().pop(obj)
del objlist
del obj

for obj,cls in zip(_objlist,_clslist):
    _cls = pickle.loads(cls)
    _obj = pickle.loads(obj)
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

    assert Z == pickle.loads(pickle.dumps(Z))
    assert Zi == pickle.loads(pickle.dumps(Zi))
    assert X == pickle.loads(pickle.dumps(X))
    assert Xi == pickle.loads(pickle.dumps(Xi))


# EOF
