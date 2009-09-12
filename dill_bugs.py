import dill

"""
c = type.__dict__
for i in c.values():
  print "%s: %s, %s" % (dill.pickles(i), type(i), i)
print ""
"""

class _d(object):
  pass

# getset_descriptor "__dict__" for new-style classes
d = _d.__dict__
for i in d.values():
  print "%s: %s, %s" % (dill.pickles(i), type(i), i)
print ""

# class instance for new-style classes
o = _d()
print "%s: %s, %s" % (dill.pickles(o), type(o), o)
print ""

