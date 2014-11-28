#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import sys
import dill
import test_mixins as module
try: from imp import reload
except ImportError: pass

cached = (module.__cached__ if hasattr(module, "__cached__")
          else module.__file__.split(".", 1)[0] + ".pyc")

module.a = 1234

pik_mod = dill.dumps(module)

module.a = 0

# remove module
del sys.modules[module.__name__]
del module

module = dill.loads(pik_mod)
assert hasattr(module, "a") and module.a == 1234
assert module.double_add(1, 2, 3) == 2 * module.fx

# Restart, and test use_diff

reload(module)

try:
    dill.use_diff()

    module.a = 1234

    pik_mod = dill.dumps(module)

    module.a = 0

    # remove module
    del sys.modules[module.__name__]
    del module

    module = dill.loads(pik_mod)
    assert hasattr(module, "a") and module.a == 1234
    assert module.double_add(1, 2, 3) == 2 * module.fx

except AttributeError:
    pass

# clean up
import os
os.remove(cached)
pycache = os.path.join(os.path.dirname(module.__file__), "__pycache__")
if os.path.exists(pycache) and not os.listdir(pycache):
    os.removedirs(pycache)
