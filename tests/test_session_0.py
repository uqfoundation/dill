#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from __future__ import print_function
import dill, sys, __main__

imported_modules = set(['json', 'urllib', 'xml.sax', 'xml.dom.minidom', 'calendar', 'cmath'])
original_modules = set(sys.modules.keys()) - imported_modules
del imported_modules

original_objects = set(__main__.__dict__.keys())
original_objects.add('original_objects')
original_objects.remove('__main__')
del __main__


# Create various kinds of objects to test different internal logics.

## Modules.
import json                             # top-level module
import urllib as url                    # top-level module under alias
from xml import sax                     # submodule
import xml.dom.minidom as dom           # submodule under alias

## Imported objects.
from calendar import Calendar, isleap, day_name     # class, function, other object
from cmath import log as complex_log                # imported with alias

## Local objects.
x = 17
empty = None
names = ['Alice', 'Bob', 'Carol']
def squared(x): return x**2
cubed = lambda x: x**3
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
person = Person(names[0], x)
class CalendarSubclass(Calendar):
    def weekdays(self):
        return [day_name[i] for i in self.iterweekdays()]
cal = CalendarSubclass()


def test_objects(main, copy_dict, byref):
    main_dict = main.__dict__

    try:
        for obj in ('json', 'url', 'sax', 'dom'):
            assert main_dict[obj].__name__ == copy_dict[obj].__name__
        
        #FIXME: In the second test call, 'calendar' is not included in
        # sys.modules, independent of the value of byref. Tried to run garbage
        # collection before with no luck. This block fails even with
        # "import calendar" before it. Needed to restore the original modules
        # with the 'copy_modules' object. (Moved to "test_session_byref_*.py".)
        #for obj in ('Calendar', 'isleap'):
        #    assert main_dict[obj] is sys.modules['calendar'].__dict__[obj]
        #assert main_dict['day_name'].__module__ == 'calendar'
        #if byref:
        #    assert main_dict['day_name'] is sys.modules['calendar'].__dict__['day_name']

        for obj in ('x', 'empty', 'names'):
            assert main_dict[obj] == copy_dict[obj]

        globs = '__globals__' if dill._dill.PY3 else 'func_globals'
        for obj in ['squared', 'cubed']:
            assert getattr(main_dict[obj], globs) is main_dict
            assert main_dict[obj](3) == copy_dict[obj](3)

        assert main_dict['Person'].__module__ == main.__name__
        assert isinstance(main_dict['person'], main_dict['Person'])
        assert main_dict['person'].age == copy_dict['person'].age

        assert issubclass(main_dict['CalendarSubclass'], main_dict['Calendar'])
        assert isinstance(main_dict['cal'], main_dict['CalendarSubclass'])
        assert main_dict['cal'].weekdays() == copy_dict['cal'].weekdays()

    except AssertionError:
        import traceback
        error_line = traceback.format_exc().splitlines()[-2].replace('[obj]', '['+repr(obj)+']')
        print("Error while testing (byref=%s):" % byref, error_line, sep="\n", file=sys.stderr)
        raise


if __name__ == '__main__':

    # Test dump_session() and load_session().
    for byref in (False, True):
        #print(sorted(set(sys.modules.keys()) - original_modules))
        dill._test_file = dill._dill.StringIO()
        try:
            # For following tests.
            dill.dump_session('session-byref-%s.pkl' % byref, byref=byref)

            dill.dump_session(dill._test_file, byref=byref)
            dump = dill._test_file.getvalue()
            dill._test_file.close()

            import __main__
            copy_dict = __main__.__dict__.copy()
            copy_modules = sys.modules.copy()
            del copy_dict['dump']
            del copy_dict['__main__']
            for name in copy_dict.keys():
                if name not in original_objects:
                    del __main__.__dict__[name]
            for module in list(sys.modules.keys()):
                if module not in original_modules:
                    del sys.modules[module]

            dill._test_file = dill._dill.StringIO(dump)
            dill.load_session(dill._test_file)
            #print(sorted(set(sys.modules.keys()) - original_modules))
        finally:
            dill._test_file.close()

        test_objects(__main__, copy_dict, byref)
        __main__.__dict__.update(copy_dict)
        sys.modules.update(copy_modules)
        del __main__, copy_dict, copy_modules, dump


    # This is for code coverage, tests the use case of dump_session(byref=True)
    # without imported objects in the namespace. It's a contrived example because
    # even dill can't be in it.
    from types import ModuleType
    main = ModuleType('__main__')
    main.x = 42

    test_file = dill._dill.StringIO()
    try:
        dill.dump_session(test_file, main=main, byref=True)
        dump = test_file.getvalue()
        test_file.close()
        test_file = dill._dill.StringIO(dump)

        # This should work after fixing https://github.com/uqfoundation/dill/issues/462
        dill.load_session(test_file)
    finally:
        test_file.close()

    assert x == 42
