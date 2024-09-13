#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2024 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import dill
dill.settings['recurse'] = True


def test_new_thread():
    import threading
    t = threading.Thread()
    t_ = dill.copy(t)
    for i in ['daemon','name','ident','native_id']:
        assert getattr(t, i) == getattr(t_, i)
        assert t.is_alive() == t_.is_alive()

def test_run_thread():
    import threading
    t = threading.Thread()
    t.start()
    t_ = dill.copy(t)
    for i in ['daemon','name','ident','native_id']:
        assert getattr(t, i) == getattr(t_, i)
        assert t.is_alive() == t_.is_alive()

def test_join_thread():
    import threading
    t = threading.Thread()
    t.start()
    t.join()
    t_ = dill.copy(t)
    for i in ['daemon','name','ident','native_id']:
        assert getattr(t, i) == getattr(t_, i)
        assert t.is_alive() == t_.is_alive()


if __name__ == '__main__':
    test_new_thread()
    test_run_thread()
    test_join_thread()
