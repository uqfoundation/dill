#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Author: Anirudh Vegesana (avegesan@cs.stanford.edu)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
test Python version tagging
"""

import dill, io, sys

def test_version_tag():
    obj = 8
    unpickler = dill.Unpickler(io.BytesIO(dill.dumps(obj)))
    obj_copy = unpickler.load()
    assert unpickler._version.python.version.hexversion == sys.hexversion


if __name__ == '__main__':
    test_version_tag()
