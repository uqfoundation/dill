#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from dill import __diff as diff


class A:
    pass

a = A()
b = A()
c = A()
a.a = b
b.a = c
diff.memorise(a)
assert not diff.has_changed(a)
c.a = 1
assert diff.has_changed(a)
diff.memorise(c, force=True)
assert not diff.has_changed(a)
c.a = 2
assert diff.has_changed(a)
changed = diff.whats_changed(a)
assert list(changed[0].keys()) == ["a"]
assert not changed[1]

a2 = []
b2 = [a2]
c2 = [b2]
diff.memorise(c2)
assert not diff.has_changed(c2)
a2.append(1)
assert diff.has_changed(c2)
changed = diff.whats_changed(c2)
assert changed[0] == {}
assert changed[1]

a3 = {}
b3 = {1: a3}
c3 = {1: b3}
diff.memorise(c3)
assert not diff.has_changed(c3)
a3[1] = 1
assert diff.has_changed(c3)
changed = diff.whats_changed(c3)
assert changed[0] == {}
assert changed[1]

try:
    import abc
    # make sure the "_abc_invaldation_counter" does not cause test to fail
    diff.memorise(abc.ABCMeta, force=True)
    assert not diff.has_changed(abc)
    abc.ABCMeta.zzz = 1
    assert diff.has_changed(abc)
    changed = diff.whats_changed(abc)
    assert list(changed[0].keys()) == ["ABCMeta"]
    assert not changed[1]
except ImportError:
    pass

'''
import Queue
diff.memorise(Queue, force=True)
assert not diff.has_changed(Queue)
Queue.Queue.zzz = 1
assert diff.has_changed(Queue)
changed = diff.whats_changed(Queue)
assert list(changed[0].keys()) == ["Queue"]
assert not changed[1]

import math
diff.memorise(math, force=True)
assert not diff.has_changed(math)
math.zzz = 1
assert diff.has_changed(math)
changed = diff.whats_changed(math)
assert list(changed[0].keys()) == ["zzz"]
assert not changed[1]
'''

a = A()
b = A()
c = A()
a.a = b
b.a = c
diff.memorise(a)
assert not diff.has_changed(a)
c.a = 1
assert diff.has_changed(a)
diff.memorise(c, force=True)
assert not diff.has_changed(a)
del c.a
assert diff.has_changed(a)
changed = diff.whats_changed(a)
assert list(changed[0].keys()) == ["a"]
assert not changed[1]
