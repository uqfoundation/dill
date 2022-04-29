#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from test_session_1_byref_false import *

if __name__ == '__main__':
    byref = True
    dill.load_session(session_file % byref)
    os.remove(session_file % byref)

    import __main__
    test_modules(__main__, byref)

    # clean up
    import test_session_1_byref_false as module
    cached = (module.__cached__ if hasattr(module, "__cached__")
            else module.__file__.split(".", 1)[0] + ".pyc")
    if os.path.exists(cached):
        os.remove(cached)
    pycache = os.path.join(os.path.dirname(module.__file__), "__pycache__")
    if os.path.exists(pycache) and not os.listdir(pycache):
        os.removedirs(pycache)
