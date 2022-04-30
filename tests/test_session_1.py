#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from __future__ import print_function
import dill, os, sys

session_file = 'session-byref-%s.pkl'

def test_modules(main, byref):
    main_dict = main.__dict__

    try:
        for obj in ('json', 'url', 'local_mod', 'sax', 'dom'):
            assert main_dict[obj].__name__ in sys.modules

        for obj in ('Calendar', 'isleap'):
            assert main_dict[obj] is sys.modules['calendar'].__dict__[obj]
        assert main.day_name.__module__ == 'calendar'
        if byref:
            assert main.day_name is sys.modules['calendar'].__dict__['day_name']

        assert main.complex_log is sys.modules['cmath'].__dict__['log']

    except AssertionError:
        import traceback
        error_line = traceback.format_exc().splitlines()[-2].replace('[obj]', '['+repr(obj)+']')
        print("Error while testing (byref=%s):" % byref, error_line, sep="\n", file=sys.stderr)
        raise

def _clean_up_cache(module):
    cached = module.__file__.split('.', 1)[0] + '.pyc'
    cached = module.__cached__ if hasattr(module, '__cached__') else cached
    pycache = os.path.join(os.path.dirname(module.__file__), '__pycache__')
    for remove, file in [(os.remove, cached), (os.removedirs, pycache)]:
        try:
            remove(file)
        except OSError:
            pass

if __name__ == '__main__':
    byref = False

    dill.load_session(session_file % byref)
    try:
        os.remove(session_file % byref)
    except OSError:
        pass

    import __main__
    test_modules(__main__, byref)
