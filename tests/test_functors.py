#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import functools
import dill

def f(a, b, c):  # without keywords
    pass

def g(a, b, c=2):  # with keywords
    pass

def h(a=1, b=2, c=3):  # without args
    pass

fp = functools.partial(f, 1, 2)
gp = functools.partial(g, 1, c=2)
hp = functools.partial(h, 1, c=2)
bp = functools.partial(int, base=2)

assert dill.pickles(fp, safe=True)
assert dill.pickles(gp, safe=True)
assert dill.pickles(hp, safe=True)
assert dill.pickles(bp, safe=True)
