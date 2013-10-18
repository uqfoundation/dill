#!/usr/bin/env python
"""
demonstrate dill's ability to pickle different python types
test pickling of all Python Standard Library objects (currently: CH 1-14 @ 2.7)
"""

import dill as pickle
#pickle.debug.trace(True)
#import pickle

# get all objects for testing
from dill.detect import load_types
load_types(pickleable=True,unpickleable=False)
#load_types(pickleable=True,unpickleable=True)
from dill.detect import objects

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

def pickles(obj,exact=False):
    """quick check if object pickles with dill"""
    try:
        pik = pickle.loads(pickle.dumps(obj))
        if exact:
            try:
                assert pik == obj
            except AssertionError, err:
                assert type(obj) == type(pik)
                print "weak: %s" % type(obj)
        else:
            assert type(obj) == type(pik)
    except Exception, err:
        print "COPY failure: %s" % type(obj)
    return


if __name__ == '__main__':

    for member in objects.values():
       #print "%s ==> %s" % (member, type(member)) # DEBUG
       #pickles(member, exact=True)
        pickles(member, exact=False)


# EOF
