"""Unpickler options must reach initialization on every interpreter."""

from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from unittest.mock import patch
import pickle

import dill


def test_ignore_option(module=dill):
    payload = pickle.dumps([1, 2, 3])
    for ignore in (None, False, True):
        assert module.loads(payload, ignore=ignore) == [1, 2, 3]
        assert module.load(BytesIO(payload), ignore=ignore) == [1, 2, 3]
        unpickler = module.Unpickler(BytesIO(payload), ignore=ignore)
        expected = dill.settings['ignore'] if ignore is None else ignore
        assert unpickler._ignore == expected
        assert unpickler.load() == [1, 2, 3]


def test_standard_options(module=dill):
    payload = b"S'\\xff'\np0\n."
    assert module.loads(payload, ignore=True, encoding='latin1') == '\xff'
    assert module.loads(payload, ignore=False, errors='replace') == '\ufffd'
    assert module.loads(pickle.dumps(42), fix_imports=False, buffers=[]) == 42


def test_unknown_option(module=dill):
    try:
        module.Unpickler(BytesIO(pickle.dumps(None)), unexpected=True)
    except TypeError:
        pass
    else:
        raise AssertionError('unknown options must still raise TypeError')


def test_out_of_band_buffers(module=dill):
    buffers = []
    payload = pickle.dumps(pickle.PickleBuffer(b'buffer data'), protocol=5,
                           buffer_callback=buffers.append)
    restored = module.loads(payload, ignore=True, buffers=buffers)
    assert memoryview(restored).tobytes() == b'buffer data'


def test_subclass_initialization(module=dill):
    class CustomUnpickler(module.Unpickler):
        def __init__(self, *args, **kwds):
            super().__init__(*args, **kwds)
            self.initialized = True

    payload = pickle.dumps([42])
    unpickler = CustomUnpickler(file=BytesIO(payload), ignore=True)
    assert isinstance(unpickler, CustomUnpickler)
    assert unpickler.initialized
    assert unpickler._ignore is True
    assert unpickler.load() == [42]


def test_allocation_initialized_unpickler():
    """Exercise unpicklers that initialize in __new__, as newer PyPy does."""
    class AllocatingUnpickler(pickle._Unpickler):
        __init__ = object.__init__

        def __new__(cls, *args, **kwds):
            unpickler = object.__new__(cls)
            pickle._Unpickler.__init__(unpickler, *args, **kwds)
            return unpickler

    spec = spec_from_file_location('dill._test_unpickler', dill._dill.__file__)
    module = module_from_spec(spec)
    with patch.object(pickle, 'Unpickler', AllocatingUnpickler):
        spec.loader.exec_module(module)

    test_ignore_option(module)
    test_standard_options(module)
    test_unknown_option(module)
    test_out_of_band_buffers(module)
    test_subclass_initialization(module)


if __name__ == '__main__':
    test_ignore_option()
    test_standard_options()
    test_unknown_option()
    test_out_of_band_buffers()
    test_subclass_initialization()
    test_allocation_initialized_unpickler()
