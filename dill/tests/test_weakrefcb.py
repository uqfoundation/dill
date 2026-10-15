#!/usr/bin/env python
#
# Author: Ilya Khalafi (@IlyaKhalafi)
# Copyright (c) 2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import gc
import weakref

import dill

dill.settings['recurse'] = True


class _class:
    pass


class _callback:
    def __init__(self):
        self.references = []

    def __call__(self, reference):
        self.references.append(reference)


def test_weakref_callback():
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        value = _class()
        callback = _callback()
        reference = weakref.ref(value, callback)
        callback.reference = reference
        restored_value, restored_reference, restored_callback = dill.loads(
            dill.dumps((value, reference, callback), protocol=protocol)
        )
        assert restored_reference() is restored_value
        assert restored_reference.__callback__ is restored_callback
        assert restored_callback.reference is restored_reference
        del restored_value
        gc.collect()
        assert restored_reference() is None
        assert restored_callback.references == [restored_reference]
        assert callback.references == []


def test_weak_collection_cleanup():
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        for collection_type in (weakref.WeakKeyDictionary, weakref.WeakSet):
            for collection_first in (False, True):
                value = _class()
                collection = collection_type({value: 42} if collection_type is weakref.WeakKeyDictionary else [value])
                value.collection = collection
                pair = (collection, value) if collection_first else (value, collection)
                first, second = dill.loads(dill.dumps(pair, protocol=protocol))
                restored_collection, restored_value = (first, second) if collection_first else (second, first)
                assert len(restored_collection) == 1
                assert restored_value in restored_collection
                assert restored_value.collection is restored_collection
                if collection_type is weakref.WeakKeyDictionary:
                    assert restored_collection[restored_value] == 42
                del first, second, restored_value
                gc.collect()
                assert len(restored_collection) == 0
                assert list(restored_collection) == []
                assert len(collection) == 1

if __name__ == '__main__':
    test_weakref_callback()
    test_weak_collection_cleanup()
