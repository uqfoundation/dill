#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import dill
dill.settings['recurse'] = True
import weakref
import gc

class _class:
    def _method(self):
        pass

class _callable_class:
    def __call__(self):
        pass


class _keyed_callback:
    def __init__(self):
        self.keys = []

    def __call__(self, reference):
        self.keys.append(reference.key)

def _function():
    pass


def test_weakref():
    o = _class()
    oc = _callable_class()
    f = _function
    x = _class

    # ReferenceType
    r = weakref.ref(o)
    d_r = weakref.ref(_class())
    fr = weakref.ref(f)
    xr = weakref.ref(x)

    # ProxyType
    p = weakref.proxy(o)
    d_p = weakref.proxy(_class())

    # CallableProxyType
    cp = weakref.proxy(oc)
    d_cp = weakref.proxy(_callable_class())
    fp = weakref.proxy(f)
    xp = weakref.proxy(x)

    objlist = [r,d_r,fr,xr, p,d_p, cp,d_cp,fp,xp]
    #dill.detect.trace(True)

    for obj in objlist:
      res = dill.detect.errors(obj)
      if res:
        print ("%r:\n  %s" % (obj, res))
    # else:
    #   print ("PASS: %s" % obj)
      assert not res

def test_dictproxy():
    from dill._dill import DictProxyType
    try:
        m = DictProxyType({"foo": "bar"})
    except Exception:
        m = type.__dict__
    mp = dill.copy(m)   
    assert mp.items() == m.items()


def test_keyed_weakrefs():
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        value = _class()
        reference = weakref.KeyedRef(value, None, 'live')
        restored_value, restored_reference = dill.loads(
            dill.dumps((value, reference), protocol=protocol)
        )
        assert type(restored_reference) is weakref.KeyedRef
        assert restored_reference() is restored_value
        assert restored_reference.key == 'live'
        assert restored_reference.__callback__ is None

        dead_value = _class()
        dead_reference = weakref.KeyedRef(dead_value, None, 'dead')
        del dead_value
        gc.collect()
        assert dead_reference() is None
        restored_dead = dill.loads(dill.dumps(dead_reference, protocol=protocol))
        gc.collect()
        assert type(restored_dead) is weakref.KeyedRef
        assert restored_dead() is None
        assert restored_dead.key == 'dead'


def test_keyed_weakref_callback():
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        value = _class()
        callback = _keyed_callback()
        reference = weakref.KeyedRef(value, callback, 'callback')
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
        assert restored_callback.keys == ['callback']
        assert callback.keys == []

        restored_reference, restored_callback = dill.loads(
            dill.dumps((reference, callback), protocol=protocol)
        )
        gc.collect()
        assert restored_reference() is None
        assert restored_callback.keys == ['callback']
        assert callback.keys == []


def test_keyed_weakref_self_key():
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        value = _class()
        reference = weakref.KeyedRef(value, None, None)
        reference.key = reference
        restored_value, restored_reference = dill.loads(
            dill.dumps((value, reference), protocol=protocol)
        )
        assert restored_reference() is restored_value
        assert restored_reference.key is restored_reference


def test_weakvalue_dictionary_cleanup():
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        for dictionary_first in (False, True):
            value = _class()
            dictionary = weakref.WeakValueDictionary({'value': value})
            value.dictionary = dictionary
            pair = (dictionary, value) if dictionary_first else (value, dictionary)
            first, second = dill.loads(dill.dumps(pair, protocol=protocol))
            restored_dictionary, restored_value = (first, second) if dictionary_first else (second, first)
            assert restored_dictionary['value'] is restored_value
            assert restored_value.dictionary is restored_dictionary
            del first, second, restored_value
            gc.collect()
            assert len(restored_dictionary) == 0


if __name__ == '__main__':
    test_weakref()
    test_keyed_weakrefs()
    test_keyed_weakref_callback()
    test_keyed_weakref_self_key()
    test_weakvalue_dictionary_cleanup()
    from dill._dill import IS_PYPY
    if not IS_PYPY:
        test_dictproxy()
