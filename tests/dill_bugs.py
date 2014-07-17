#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE
"""
demonstrate current bugs in some of dill's advanced features
"""

import dill

"""
c = type.__dict__
for i in c.values():
  print ("%s: %s, %s" % (dill.pickles(i), type(i), i))
print ("")
"""

def _g(x): yield x;

def _f():
  try: raise
  except:
    from sys import exc_info
    e, er, tb = exc_info()
    return er, tb

class _d(object):
  def _method(self):
    pass

from dill import objects
from dill import load_types
load_types(pickleable=True,unpickleable=False)
_newclass = objects['ClassObjectType']
del objects

# getset_descriptor for new-style classes (fails on '_method', if not __main__)
d = _d.__dict__
for i in d.values():
  print ("%s: %s, %s" % (dill.pickles(i), type(i), i))
print ("")
od = _newclass.__dict__
for i in od.values():
  print ("%s: %s, %s" % (dill.pickles(i), type(i), i))
print ("")

"""
# (__main__) class instance for new-style classes
o = _d()
oo = _newclass()
print ("%s: %s, %s" % (dill.pickles(o), type(o), o))
print ("%s: %s, %s" % (dill.pickles(oo), type(oo), oo))
print ("")
"""

# frames, generators, and tracebacks (all depend on frame)
g = _g(1)
f = g.gi_frame
e,t = _f()
print ("%s: %s, %s" % (dill.pickles(f), type(f), f))
print ("%s: %s, %s" % (dill.pickles(g), type(g), g))
print ("%s: %s, %s" % (dill.pickles(t), type(t), t))
print ("%s: %s, %s" % (dill.pickles(e), type(e), e))
print ("")

