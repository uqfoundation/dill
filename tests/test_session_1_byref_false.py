#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from __future__ import print_function
import dill, os, sys

session_file = 'session-byref-%s.pkl'

def test_modules(main, byref):
    main_dict = main.__dict__

    try:
        for obj in ('json', 'url', 'sax', 'dom'):
            assert main_dict[obj].__name__ in sys.modules

        for obj in ('Calendar', 'isleap'):
            assert main_dict[obj] is sys.modules['calendar'].__dict__[obj]
        assert main_dict['day_name'].__module__ == 'calendar'
        if byref:
            assert main_dict['day_name'] is sys.modules['calendar'].__dict__['day_name']

        assert main_dict['complex_log'] is sys.modules['cmath'].__dict__['log']

    except AssertionError:
        import traceback
        error_line = traceback.format_exc().splitlines()[-2].replace('[obj]', '['+repr(obj)+']')
        print("Error while testing (byref=%s):" % byref, error_line, sep="\n", file=sys.stderr)
        raise

if __name__ == '__main__':
    byref = False
    dill.load_session(session_file % byref)
    os.remove(session_file % byref)

    import __main__
    test_modules(__main__, byref)
