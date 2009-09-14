import dill

"""
c = type.__dict__
for i in c.values():
  print "%s: %s, %s" % (dill.pickles(i), type(i), i)
print ""
"""

class _d(object):
  pass

def _g(x): yield x;

def _f():
  try: raise
  except:
    from sys import exc_info
    e, er, tb = exc_info()
    return er, tb

# getset_descriptor "__dict__" for new-style classes
d = _d.__dict__
for i in d.values():
  print "%s: %s, %s" % (dill.pickles(i), type(i), i)
print ""

# class instance for new-style classes
o = _d()
print "%s: %s, %s" % (dill.pickles(o), type(o), o)
print ""

# frames, generators, and tracebacks (all depend on frame)
g = _g(1)
f = g.gi_frame
e,t = _f()
print "%s: %s, %s" % (dill.pickles(f), type(f), f)
print "%s: %s, %s" % (dill.pickles(g), type(g), g)
print "%s: %s, %s" % (dill.pickles(t), type(t), t)
print "%s: %s, %s" % (dill.pickles(e), type(e), e)
print ""

