#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import sys
import dill
import test_mixins as module

cached = (module.__cached__ if hasattr(module, "__cached__")
          else module.__file__ + "c")

module.a = 1234

pik_mod = dill.dumps(module)

module.a = 0

# remove module
del sys.modules[module.__name__]
del module

module = dill.loads(pik_mod)
assert hasattr(module, "a") and module.a == 1234
assert module.double_add(1, 2, 3) == 2 * module.fx

# clean up
import os
os.remove(cached)
if os.path.exists("__pycache__") and not os.listdir("__pycache__"):
    os.removedirs("__pycache__")
