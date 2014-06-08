#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from dill.detect import baditems, badobjects, badtypes, errors, parent, at

import inspect

f = inspect.currentframe()
assert baditems(f) == [f]
#assert baditems(globals()) == [f] #XXX
assert badobjects(f) is f
assert badtypes(f) == type(f)
assert isinstance(errors(f), TypeError)
d = badtypes(f, 1)
assert isinstance(d, dict)
assert list(badobjects(f, 1).keys()) == list(d.keys())
assert list(errors(f, 1).keys()) == list(d.keys())
assert len(set([err.args[0] for err in list(errors(f, 1).values())])) is 1

x = [4,5,6,7]
listiter = iter(x)
obj = parent(listiter, list)
assert obj is x

assert parent(obj, int) is x[-1]
assert at(id(at)) is at

