#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill

def f(func):
  def w(*args):
    return f(*args)
  return w

@f
def f2(): pass

# check when __main__ and on import
assert dill.pickles(f2)


import doctest
import logging
logging.basicConfig(level=logging.DEBUG)

class SomeUnreferencedUnpicklableClass(object):
    def __reduce__(self):
        raise Exception

unpicklable = SomeUnreferencedUnpicklableClass()

# This works fine outside of Doctest:
serialized = dill.dumps(lambda x: x)

# should not try to pickle unpicklable object in __globals__
def tests():
    """
    >>> serialized = dill.dumps(lambda x: x)
    """
    return

#print("\n\nRunning Doctest:")
doctest.testmod()
