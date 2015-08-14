from __future__ import with_statement
from dill import check
from dill.temp import capture
from dill.dill import PY3
import sys

f = lambda x:x**2

#FIXME: this doesn't catch output... it's from the internal call
def test(func, **kwds):
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


if __name__ == '__main__':
    test(f)
    test(f, recurse=True)
    test(f, byref=True)
    test(f, protocol=0)
    #TODO: test incompatible versions
    # SyntaxError: invalid syntax
    if PY3:
        test(f, python='python3.4')
    else:
        test(f, python='python2.7')
    #TODO: test dump failure
    #TODO: test load failure


# EOF
