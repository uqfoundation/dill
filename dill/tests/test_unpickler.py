"""Unpickler options must reach initialization on every interpreter."""

from io import BytesIO
import pickle

import dill


def test_ignore_option():
    payload = pickle.dumps([1, 2, 3])
    for ignore in (None, False, True):
        assert dill.loads(payload, ignore=ignore) == [1, 2, 3]
        assert dill.load(BytesIO(payload), ignore=ignore) == [1, 2, 3]
        unpickler = dill.Unpickler(BytesIO(payload), ignore=ignore)
        expected = dill.settings['ignore'] if ignore is None else ignore
        assert unpickler._ignore == expected
        assert unpickler.load() == [1, 2, 3]


def test_standard_options():
    payload = b"S'\\xff'\np0\n."
    assert dill.loads(payload, ignore=True, encoding='latin1') == '\xff'
    assert dill.loads(payload, ignore=False, errors='replace') == '\ufffd'
    assert dill.loads(pickle.dumps(42), fix_imports=False, buffers=[]) == 42


def test_unknown_option():
    try:
        dill.Unpickler(BytesIO(pickle.dumps(None)), unexpected=True)
    except TypeError:
        pass
    else:
        raise AssertionError('unknown options must still raise TypeError')


def test_out_of_band_buffers():
    buffers = []
    payload = pickle.dumps(pickle.PickleBuffer(b'buffer data'), protocol=5,
                           buffer_callback=buffers.append)
    restored = dill.loads(payload, ignore=True, buffers=buffers)
    assert memoryview(restored).tobytes() == b'buffer data'


def test_subclass_initialization():
    class CustomUnpickler(dill.Unpickler):
        def __init__(self, *args, **kwds):
            super().__init__(*args, **kwds)
            self.initialized = True

    payload = pickle.dumps([42])
    unpickler = CustomUnpickler(file=BytesIO(payload), ignore=True)
    assert isinstance(unpickler, CustomUnpickler)
    assert unpickler.initialized
    assert unpickler._ignore is True
    assert unpickler.load() == [42]


if __name__ == '__main__':
    test_ignore_option()
    test_standard_options()
    test_unknown_option()
    test_out_of_band_buffers()
    test_subclass_initialization()
