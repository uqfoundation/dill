from dill.detect import badobjects, badtypes, errors, parent

import inspect

f = inspect.currentframe()
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

