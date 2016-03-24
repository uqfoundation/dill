#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from dill.detect import baditems, badobjects, badtypes, errors, parent, at, globalvars
from dill import settings

import inspect

f = inspect.currentframe()
assert baditems(f) == [f]
#assert baditems(globals()) == [f] #XXX
assert badobjects(f) is f
assert badtypes(f) == type(f)
assert isinstance(errors(f), TypeError) #FIXME: pypy
# print (errors(f))
# Can't pickle <class 'app_main.CommandLineError'>: it's not found as app_main.CommandLineError
d = badtypes(f, 1)
assert isinstance(d, dict)
assert list(badobjects(f, 1).keys()) == list(d.keys())
assert list(errors(f, 1).keys()) == list(d.keys())
s = set([(err.__class__.__name__,err.args[0]) for err in list(errors(f, 1).values())])
a = dict(s)
assert len(s) is len(a) # TypeError (and possibly PicklingError)
assert len(a) is 2 if 'PicklingError' in a.keys() else 1

x = [4,5,6,7]
listiter = iter(x)
obj = parent(listiter, list)
assert obj is x

assert parent(obj, int) is x[-1] #FIXME: pypy
# print (parent(obj, int), x[-1])
assert at(id(at)) is at

def f():
    a
    def g():
        b
        def h():
            c
a, b, c = 1, 2, 3
assert globalvars(f) == dict(a=1, b=2, c=3)

def squared(x):
  return a+x**2

def foo(x):
  def bar(y):
    return squared(x)+y
  return bar

class _class:
    def _method(self):
        pass
    def ok(self):
        return True

res = globalvars(foo, recurse=True)
assert set(res) == set(['squared', 'a'])
res = globalvars(foo, recurse=False)
assert res == {}
zap = foo(2)
res = globalvars(zap, recurse=True)
assert set(res) == set(['squared', 'a'])
res = globalvars(zap, recurse=False)
assert set(res) == set(['squared'])
del zap
res = globalvars(squared)
assert set(res) == set(['a'])
# FIXME: should find referenced __builtins__
#res = globalvars(_class, recurse=True)
#assert set(res) == set(['True'])
#res = globalvars(_class, recurse=False)
#assert res == {}
#res = globalvars(_class.ok, recurse=True)
#assert set(res) == set(['True'])
#res = globalvars(_class.ok, recurse=False)
#assert set(res) == set(['True'])


#98 dill ignores __getstate__ in interactive lambdas
bar = [0]

class Foo(object):
    def __init__(self):
        pass
    def __getstate__(self):
        bar[0] = bar[0]+1
        return {}
    def __setstate__(self, data):
        pass

f = Foo()
from dill import dumps, loads
dumps(f)
dumps(lambda: f, recurse=False) # doesn't call __getstate__
dumps(lambda: f, recurse=True) # calls __getstate__
assert bar[0] == 2


#97 serialize lambdas in test files
from math import sin, pi
def sinc(x):
    return sin(x)/x

settings['recurse'] = True
_sinc = dumps(sinc)
del sin
sinc_ = loads(_sinc) # no NameError... pickling preserves 'sin'
res = sinc_(1)
from math import sin
assert sinc(1) == res


