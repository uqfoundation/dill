#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
demonstrate dill's ability to pickle different python types
test pickling of all Python Standard Library objects (currently: CH 1-14 @ 2.7)
"""

import dill as pickle
pickle.settings['recurse'] = True
#pickle.detect.trace(True)
#import pickle

# get all objects for testing
from dill import load_types, objects, extend
load_types(pickleable=True,unpickleable=False)

import warnings

# uncomment the next two lines to test cloudpickle
#extend(False)
#import cloudpickle as pickle

# helper objects
class _class:
    def _method(self):
        pass

# objects that *fail* if imported
special = {}
special['LambdaType'] = _lambda = lambda x: lambda y: x
special['MethodType'] = _method = _class()._method
special['UnboundMethodType'] = _class._method
objects.update(special)

def pickles(name, exact=False):
    """quick check if object pickles with dill"""
    obj = objects[name]
    try:
        pik = pickle.loads(pickle.dumps(obj))
        if exact:
            try:
                assert pik == obj
            except AssertionError:
                assert type(obj) == type(pik)
                print ("weak: %s %s" % (name, type(obj)))
        else:
            assert type(obj) == type(pik)
    except Exception:
        print ("fails: %s %s" % (name, type(obj)))


def test_objects():
    for member in objects.keys():
       #pickles(member, exact=True)
        pickles(member, exact=False)

test_pycapsule = None

if pickle._dill.HAS_CTYPES:
    import ctypes
    if hasattr(ctypes, 'pythonapi'):
        def test_pycapsule():
            name = ctypes.create_string_buffer(b'dill._testcapsule')
            capsule = pickle._dill._PyCapsule_New(
                ctypes.cast(pickle._dill._PyCapsule_New, ctypes.c_void_p),
                name,
                None
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pickle.copy(capsule)
            pickle._testcapsule = capsule
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pickle.copy(capsule)
            pickle._testcapsule = None
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", pickle.PicklingWarning)
                    pickle.copy(capsule)
            except pickle.UnpicklingError:
                pass
            else:
                raise AssertionError("Expected a different error")

if __name__ == '__main__':
    test_objects()
    if test_pycapsule is not None:
        test_pycapsule()
