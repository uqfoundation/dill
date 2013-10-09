#!/usr/bin/env python
"""
all Python Standard Library object types (currently: CH 1-14 @ 2.7)
and some other common object types (i.e. numpy.ndarray)
"""

from detect import objects # local import of dill.detect
for _type in objects.keys():
    exec "%s = type(objects['%s'])" % (_type,_type)
    
del objects
try:
    del _type
except NameError:
    pass
