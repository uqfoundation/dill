#!/usr/bin/env python
"""
all Python Standard Library object types (currently: CH 1-14 @ 2.7)
and some other common types (i.e. numpy.ndarray)
"""

# get all objects for testing
from objects import succeeds as test_objects
from objects import failures
test_objects.update(failures)


# generate types from objects
for _type in test_objects.keys():
    exec "%s = type(test_objects['%s'])" % (_type,_type)

del _type, test_objects, failures


# EOF
