#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2024-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import dill
import threading
import warnings

dill.settings['recurse'] = True


def _thread_getstate(self):
    state = self.__dict__.copy()
    state.pop('_stderr', None)
    state.pop('_context', None)
    return state


def _thread_setstate(self, state):
    self.__dict__.update(state)


threading.Thread.__getstate__ = _thread_getstate
threading.Thread.__setstate__ = _thread_setstate


def _copy_thread(thread):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', ResourceWarning)
        cloned = dill.copy(thread)
    resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
    assert not resource_warnings, resource_warnings[0].message if resource_warnings else None
    return cloned


def _check_thread(thread, cloned):
    assert type(cloned) is type(thread)
    for attr in ['daemon', 'name', 'ident', 'native_id']:
        if hasattr(thread, attr):
            assert getattr(cloned, attr) == getattr(thread, attr)


def test_new_thread():
    t = threading.Thread()
    t_ = _copy_thread(t)
    _check_thread(t, t_)
    assert not t.is_alive()
    assert not t_.is_alive()


def test_run_thread():
    t = threading.Thread()
    t.start()
    t_ = _copy_thread(t)
    _check_thread(t, t_)
    t.join()


def test_join_thread():
    t = threading.Thread()
    t.start()
    t.join()
    t_ = _copy_thread(t)
    _check_thread(t, t_)


if __name__ == '__main__':
    test_new_thread()
    test_run_thread()
    test_join_thread()
