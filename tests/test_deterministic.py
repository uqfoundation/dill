import collections
import dill
import warnings

b = 5
a = 0
c = 7

def test_determinism():
    def f():
        global a, b, c
        return a + b + c

    d1 = {'a': 0, 'c': 7, 'b': 5, '__name__': __name__, '__builtins__': __builtins__}
    d2 = {'a': 0, 'b': 5, 'c': 7, '__name__': __name__, '__builtins__': __builtins__}
    assert dill.dumps(d1) != dill.dumps(d2)

    F1 = dill.dumps(f, recurse=True)
    F1D = dill.dumps(f, recurse=True, deterministic=True)

    qual = f.__qualname__
    f = dill._dill.FunctionType(f.__code__, d1, f.__name__, f.__defaults__, f.__closure__)
    f.__qualname__ = qual
    f.__module__ = '__main__'

    assert f.__globals__ is d1

    F2 = dill.dumps(f, recurse=True)
    F2D = dill.dumps(f, recurse=True, deterministic=True)

    f = dill._dill.FunctionType(f.__code__, d2, f.__name__, f.__defaults__, f.__closure__)
    f.__qualname__ = qual
    f.__module__ = '__main__'

    assert f.__globals__ is d2

    F3 = dill.dumps(f, recurse=True)
    F3D = dill.dumps(f, recurse=True, deterministic=True)

    # TODO: actually create a test to verify that the globals are sorted. The
    # globalvars function gets the globals dictionary from the module, not the
    # function itself, so they will all have the same global namespace.
    # assert F2 != F3
    # assert F1 != F1D
    assert F1D == F2D
    assert F2D == F3D

    a = {2-1j,2+1j,1+2j,1-2j}
    b = a.copy()
    b.add(-2)
    b.remove(-2)
    if not dill._dill.IS_PYPY:
        assert list(a) != list(b)
    assert dill.dumps(a, deterministic=True) == dill.dumps(b, deterministic=True)

if __name__ == '__main__':
    if dill._dill.PY3:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", dill.PickleWarning)
            test_determinism()
