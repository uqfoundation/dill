#!/usr/bin/env python
"""
all Python Standard Library object types (currently: CH 1-15 @ 2.7)
and some other common object types (i.e. numpy.ndarray)

to load more objects and types, use dill.load_types()
"""

from __future__ import absolute_import

# non-local import of dill.objects
from dill import objects
for _type in objects.keys():
    exec("%s = type(objects['%s'])" % (_type,_type))
    
del objects
try:
    del _type
except NameError:
    pass

del absolute_import
