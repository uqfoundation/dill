#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2024-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import dill
dill.settings['recurse'] = True


def test_new_thread():
    import threading
    t = threading.Thread()
    t_ = dill.copy(t)
    assert t.is_alive() == t_.is_alive()
    for i in ['daemon','name','ident','native_id']:
        if hasattr(t, i):
            assert getattr(t, i) == getattr(t_, i)

def test_run_thread():
    import threading
    t = threading.Thread()
    t.start()
    t_ = dill.copy(t)
    assert t.is_alive() == t_.is_alive()
    for i in ['daemon','name','ident','native_id']:
        if hasattr(t, i):
            assert getattr(t, i) == getattr(t_, i)

def test_join_thread():
    import threading
    t = threading.Thread()
    t.start()
    t.join()
    t_ = dill.copy(t)
    assert t.is_alive() == t_.is_alive()
    for i in ['daemon','name','ident','native_id']:
        if hasattr(t, i):
            assert getattr(t, i) == getattr(t_, i)


def _acquire_from_thread(lock):
    import threading
    acquired = []

    def acquire():
        acquired.append(lock.acquire(timeout=0.1))
        if acquired[-1]:
            lock.release()

    thread = threading.Thread(target=acquire)
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive()
    return acquired == [True]


def test_unheld_rlock():
    import threading
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        for released in (False, True):
            lock = threading.RLock()
            if released:
                lock.acquire()
                lock.release()
            restored = dill.loads(dill.dumps(lock, protocol=protocol))
            assert not restored._is_owned()
            assert restored.acquire(timeout=0.1)
            restored.release()
            assert _acquire_from_thread(restored)


def test_held_rlock():
    import threading
    for count in (1, 2, 5):
        lock = threading.RLock()
        for _ in range(count):
            lock.acquire()
        try:
            restored = dill.copy(lock)
            assert lock._is_owned()
            assert restored._is_owned()
            assert not _acquire_from_thread(restored)
            for remaining in range(count - 1, -1, -1):
                restored.release()
                assert restored._is_owned() == bool(remaining)
            try:
                restored.release()
            except RuntimeError:
                pass
            else:
                raise AssertionError("Released an unheld RLock")
            assert _acquire_from_thread(restored)
        finally:
            for _ in range(count):
                lock.release()
        assert not lock._is_owned()


def test_rlock_owner():
    import threading
    lock = threading.RLock()
    lock.acquire()
    errors = []
    try:
        data = dill.dumps(lock)

        def restore():
            try:
                lock.release()
            except RuntimeError:
                errors.append('release')
            try:
                dill.loads(data)
            except dill.UnpicklingError:
                errors.append('restore')

        thread = threading.Thread(target=restore)
        thread.start()
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert errors == ['release', 'restore']
        assert lock._is_owned()
    finally:
        lock.release()


def test_cookiejar_lock():
    from http.cookiejar import CookieJar
    restored = dill.copy(CookieJar())
    assert restored._cookies_lock.acquire(timeout=0.1)
    restored._cookies_lock.release()


if __name__ == '__main__':
    test_new_thread()
    test_run_thread()
    test_join_thread()
    test_unheld_rlock()
    test_held_rlock()
    test_rlock_owner()
    test_cookiejar_lock()
