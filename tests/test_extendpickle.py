#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill as pickle
try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO

def my_fn(x):
    return x * 17

def test_extend():
    obj = lambda : my_fn(34)
    assert obj() == 578

    obj_io = StringIO()
    pickler = pickle.Pickler(obj_io)
    pickler.dump(obj)

    obj_str = obj_io.getvalue()

    obj2_io = StringIO(obj_str)
    unpickler = pickle.Unpickler(obj2_io)
    obj2 = unpickler.load()

    assert obj2() == 578
