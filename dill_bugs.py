import dill

"""
c = type.__dict__
for i in c.values():
  print "%s: %s, %s" % (dill.pickles(i), type(i), i)
print ""
"""

def _g(x): yield x;

def _f():
  try: raise
  except:
    from sys import exc_info
    e, er, tb = exc_info()
    return er, tb

class _d(object):
  pass

from dill_test2 import _newclass

# getset_descriptor "__dict__" for new-style classes
d = _d.__dict__
for i in d.values():
  print "%s: %s, %s" % (dill.pickles(i), type(i), i)
print ""
#od = _newclass.__dict__
#for i in od.values():
#  print "%s: %s, %s" % (dill.pickles(i), type(i), i)
#print ""

"""
# (__main__) class instance for new-style classes
o = _d()
oo = _newclass()
print "%s: %s, %s" % (dill.pickles(o), type(o), o)
print "%s: %s, %s" % (dill.pickles(oo), type(oo), oo)
print ""
"""

# frames, generators, and tracebacks (all depend on frame)
g = _g(1)
f = g.gi_frame
e,t = _f()
print "%s: %s, %s" % (dill.pickles(f), type(f), f)
print "%s: %s, %s" % (dill.pickles(g), type(g), g)
print "%s: %s, %s" % (dill.pickles(t), type(t), t)
print "%s: %s, %s" % (dill.pickles(e), type(e), e)
print ""

