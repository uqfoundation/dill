#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from dill import memorise as m


class A:
    pass

a = A()
b = A()
c = A()
a.a = b
b.a = c
m.memorise(a)
assert not m.has_changed(a)
c.a = 1
assert m.has_changed(a)
m.memorise(c, force=True)
assert not m.has_changed(a)
c.a = 2
assert m.has_changed(a)
changed = m.whats_changed(a)
assert list(changed[0].keys()) == ["a"]
assert not changed[1]

a2 = []
b2 = [a2]
c2 = [b2]
m.memorise(c2)
assert not m.has_changed(c2)
a2.append(1)
assert m.has_changed(c2)
changed = m.whats_changed(c2)
assert changed[0] == {}
assert changed[1]

a3 = {}
b3 = {1: a3}
c3 = {1: b3}
m.memorise(c3)
assert not m.has_changed(c3)
a3[1] = 1
assert m.has_changed(c3)
changed = m.whats_changed(c3)
assert changed[0] == {}
assert changed[1]

import abc
# make sure that the "_abc_invaldation_counter" does not cause the test to fail
m.memorise(abc.ABCMeta, force=True)
assert not m.has_changed(abc)
abc.ABCMeta.zzz = 1
assert m.has_changed(abc)
changed = m.whats_changed(abc)
assert list(changed[0].keys()) == ["ABCMeta"]
assert not changed[1]


a = A()
b = A()
c = A()
a.a = b
b.a = c
m.memorise(a)
assert not m.has_changed(a)
c.a = 1
assert m.has_changed(a)
m.memorise(c, force=True)
assert not m.has_changed(a)
del c.a
assert m.has_changed(a)
changed = m.whats_changed(a)
assert list(changed[0].keys()) == ["a"]
assert not changed[1]
