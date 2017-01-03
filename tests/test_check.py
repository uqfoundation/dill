#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from __future__ import with_statement
from dill import check
from dill.temp import capture
from dill.dill import PY3
import sys

f = lambda x:x**2


# FIXME: this doesn't catch output... it's from the internal call
def no_exception_raised(func, **kwds):
    try:
        with capture('stdout') as out:
            check(func, **kwds)
    except Exception:
        e = sys.exc_info()[1]
        raise AssertionError(str(e))
    else:
        assert 'Traceback' not in out.getvalue()
    finally:
        out.close()


def test_check():
    no_exception_raised(f)
    no_exception_raised(f, recurse=True)
    no_exception_raised(f, byref=True)
    no_exception_raised(f, protocol=0)
    # TODO: test incompatible versions
    # SyntaxError: invalid syntax
    if PY3:
        no_exception_raised(f, python='python3.4')
    else:
        no_exception_raised(f, python='python2.7')
    # TODO: test dump failure
    # TODO: test load failure


if __name__ == '__main__':
    test_check()

# EOF
