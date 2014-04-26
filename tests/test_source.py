#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from dill.source import getsource, getname, _wrap, likely_import
from dill.source import getimportable


import sys
PY3 = sys.version_info[0] >= 3

f = lambda x: x**2
def g(x): return f(x) - x

def h(x):
  def g(x): return x
  return g(x) - x 

class Foo(object):
  def bar(self, x):
    return x*x+x
_foo = Foo()

def add(x,y):
  return x+y

# yes, same as 'f', but things are tricky when it comes to pointers
squared = lambda x:x**2

class Bar:
  pass
_bar = Bar()

                       # inspect.getsourcelines # dill.source.getblocks
assert getsource(f) == 'f = lambda x: x**2\n'
assert getsource(g) == 'def g(x): return f(x) - x\n'
assert getsource(h) == 'def h(x):\n  def g(x): return x\n  return g(x) - x \n'
assert getname(f) == 'f'
assert getname(g) == 'g'
assert getname(h) == 'h'
assert _wrap(f)(4) == 16
assert _wrap(g)(4) == 12
assert _wrap(h)(4) == 0

assert getname(Foo) == 'Foo'
assert getname(Bar) == 'Bar'
assert getsource(Bar) == 'class Bar:\n  pass\n'
assert getsource(Foo) == 'class Foo(object):\n  def bar(self, x):\n    return x*x+x\n'
#XXX: add getsource for  _foo, _bar

assert getimportable(add) == 'from %s import add\n' % __name__
assert getimportable(squared) == 'from %s import squared\n' % __name__
assert getimportable(Foo) == 'from %s import Foo\n' % __name__
assert getimportable(Foo.bar) == 'from %s import bar\n' % __name__
assert getimportable(_foo.bar) == 'from %s import bar\n' % __name__
assert getimportable(None) == 'None\n'
assert getimportable(100) == '100\n'

assert getimportable(add, byname=False) == 'def add(x,y):\n  return x+y\n'
assert getimportable(squared, byname=False) == 'squared = lambda x:x**2\n'
assert getimportable(None, byname=False) == 'None\n'
assert getimportable(Bar, byname=False) == 'class Bar:\n  pass\n'
assert getimportable(Foo, byname=False) == 'class Foo(object):\n  def bar(self, x):\n    return x*x+x\n'
assert getimportable(Foo.bar, byname=False) == 'def bar(self, x):\n  return x*x+x\n'
assert getimportable(Foo.bar, byname=True) == 'from %s import bar\n' % __name__
assert getimportable(Foo.bar, alias='memo', byname=True) == 'from %s import bar as memo\n' % __name__
assert getimportable(_foo, byname=False).startswith("import dill\nclass Foo(object):\n  def bar(self, x):\n    return x*x+x\ndill.loads(")
assert getimportable(Foo, alias='memo', byname=True) == 'from %s import Foo as memo\n' % __name__
assert getimportable(squared, alias='memo', byname=True) == 'from %s import squared as memo\n' % __name__
assert getimportable(squared, alias='memo', byname=False) == 'memo = squared = lambda x:x**2\n'
assert getimportable(add, alias='memo', byname=False) == 'def add(x,y):\n  return x+y\n\nmemo = add\n'
assert getimportable(None, alias='memo', byname=False) == 'memo = None\n'
assert getimportable(100, alias='memo', byname=False) == 'memo = 100\n'
assert getimportable(add, explicit=True) == 'from %s import add\n' % __name__
assert getimportable(squared, explicit=True) == 'from %s import squared\n' % __name__
assert getimportable(Foo, explicit=True) == 'from %s import Foo\n' % __name__
assert getimportable(Foo.bar, explicit=True) == 'from %s import bar\n' % __name__
assert getimportable(_foo.bar, explicit=True) == 'from %s import bar\n' % __name__
assert getimportable(None, explicit=True) == 'None\n'
assert getimportable(100, explicit=True) == '100\n'


try:
    from numpy import array
    x = array([1,2,3])
    assert getimportable(x) == 'from numpy import array\narray([1, 2, 3])\n'
    assert getimportable(array) == 'from numpy.core.multiarray import array\n'
    assert getimportable(x, byname=False) == 'from numpy import array\narray([1, 2, 3])\n'
    assert getimportable(array, byname=False) == 'from numpy.core.multiarray import array\n'
except ImportError: pass

# test itself
assert likely_import(likely_import)=='from dill.source import likely_import\n'

# builtin functions and objects
if PY3: builtin = 'builtins'
else: builtin = '__builtin__'
assert likely_import(pow) == 'pow\n'
assert likely_import(100) == '100\n'
assert likely_import(True) == 'True\n'
assert likely_import(pow, explicit=True) == 'from %s import pow\n' % builtin
assert likely_import(100, explicit=True) == '100\n'
assert likely_import(True, explicit=True) == 'True\n' if PY3 else 'from %s import True\n' % builtin
# this is kinda BS... you can't import a None
assert likely_import(None) == 'None\n'
assert likely_import(None, explicit=True) == 'None\n'

# other imported functions
from math import sin
assert likely_import(sin) == 'from math import sin\n'

# interactively defined functions
assert likely_import(add) == 'from %s import add\n' % __name__

# interactive lambdas
assert likely_import(squared) == 'from %s import squared\n' % __name__

# classes and class instances
try: #XXX: should this be a 'special case'?
    from StringIO import StringIO
    x = "from StringIO import StringIO\n"
    y = x
except ImportError:
    from io import BytesIO as StringIO
    x = "from io import BytesIO\n"
    y = "from _io import BytesIO\n"
s = StringIO()
assert likely_import(StringIO) == x
assert likely_import(s) == y

# interactively defined classes and class instances
assert likely_import(Foo) == 'from %s import Foo\n' % __name__
assert likely_import(_foo) == 'from %s import Foo\n' % __name__


# EOF
