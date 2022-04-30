#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from test_session_1 import *

if __name__ == '__main__':
    byref = True

    dill.load_session(session_file % byref)
    try:
        os.remove(session_file % byref)
    except OSError:
        pass

    import __main__
    test_modules(__main__, byref)

    # clean up
    import test_session_1 as module
    module._clean_up_cache(module)
