#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from __future__ import with_statement
import sys

from dill import dumps
from dill.temp import capture
from dill.dill import PY3


def check(obj, *args, **kwds):
    """check pickling of an object across another process"""
   # == undocumented ==
   # python -- the string path or executable name of the selected python
   # verbose -- if True, be verbose about printing warning messages
   # all other args and kwds are passed to dill.dumps
    verbose = kwds.pop('verbose', False)
    python = kwds.pop('python', None)
    if python is None:
        import sys
        python = sys.executable
    # type check
    isinstance(python, str)
    import subprocess
    fail = True
    try:
        _obj = dumps(obj, *args, **kwds)
        fail = False
    finally:
        if fail and verbose:
            print("DUMP FAILED")
    msg = "%s -c import dill; print(dill.loads(%s))" % (python, repr(_obj))
    msg = "SUCCESS" if not subprocess.call(msg.split(None, 2)) else "FAILED"
    if verbose:
        print(msg)
    return


#FIXME: this doesn't catch output... it's from the internal call
def raise_check(func, **kwds):
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


f = lambda x:x**2


def test_simple():
    raise_check(f)


def test_recurse():
    raise_check(f, recurse=True)


def test_byref():
    raise_check(f, byref=True)


def test_protocol():
    raise_check(f, protocol=True)


def test_python():
    if PY3:
        raise_check(f, python='python3.4')
    else:
        raise_check(f, python='python2.7')


#TODO: test incompatible versions
#TODO: test dump failure
#TODO: test load failure
