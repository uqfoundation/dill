#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from __future__ import print_function
import atexit, dill, os, sys, __main__

session_file = os.path.join(os.path.dirname(__file__), 'session-byref-%s.pkl')

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


# Test session loading in a fresh interpreter session.
if __name__ == '__main__' and len(sys.argv) >= 3 and sys.argv[1] == '--child':
    byref = sys.argv[2] == 'True'
    dill.load_session(session_file % byref)
    test_modules(__main__, byref)
    sys.exit()

del test_modules


def _clean_up_cache(module):
    cached = module.__file__.split('.', 1)[0] + '.pyc'
    cached = module.__cached__ if hasattr(module, '__cached__') else cached
    pycache = os.path.join(os.path.dirname(module.__file__), '__pycache__')
    for remove, file in [(os.remove, cached), (os.removedirs, pycache)]:
        try:
            remove(file)
        except OSError:
            pass


# To clean up namespace before loading the session.
original_modules = set(sys.modules.keys()) - \
        set(['json', 'urllib', 'xml.sax', 'xml.dom.minidom', 'calendar', 'cmath'])
original_objects = set(__main__.__dict__.keys())
original_objects.add('original_objects')


# Create various kinds of objects to test different internal logics.

## Modules.
import json                                         # top-level module
import urllib as url                                # top-level module under alias
from xml import sax                                 # submodule
import xml.dom.minidom as dom                       # submodule under alias
import test_dictviews as local_mod                  # non-builtin top-level module
atexit.register(_clean_up_cache, local_mod)

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
selfref = __main__


def test_objects(main, copy_dict, byref):
    main_dict = main.__dict__

    try:
        for obj in ('json', 'url', 'local_mod', 'sax', 'dom'):
            assert main_dict[obj].__name__ == copy_dict[obj].__name__

        #FIXME: In the second test call, 'calendar' is not included in
        # sys.modules, independent of the value of byref. Tried to run garbage
        # collection before with no luck. This block fails even with
        # "import calendar" before it. Needed to restore the original modules
        # with the 'copy_modules' object. (Moved to "test_session_{1,2}.py".)

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

        assert main.Person.__module__ == main.__name__
        assert isinstance(main.person, main.Person)
        assert main.person.age == copy_dict['person'].age

        assert issubclass(main.CalendarSubclass, main.Calendar)
        assert isinstance(main.cal, main.CalendarSubclass)
        assert main.cal.weekdays() == copy_dict['cal'].weekdays()

        assert main.selfref is main

    except AssertionError:
        import traceback
        error_line = traceback.format_exc().splitlines()[-2].replace('[obj]', '['+repr(obj)+']')
        print("Error while testing (byref=%s):" % byref, error_line, sep="\n", file=sys.stderr)
        raise


if __name__ == '__main__':

    # Test dump_session() and load_session().
    for byref in (False, True):
        if byref:
            # Test unpickleable imported object in main.
            from sys import flags

        #print(sorted(set(sys.modules.keys()) - original_modules))
        dill._test_file = dill._dill.StringIO()
        try:
            # For the subprocess.
            dill.dump_session(session_file % byref, byref=byref)

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

            # Test session loading in a new session.
            from dill.tests.__main__ import python, shell, sp
            error = sp.call([python, __file__, '--child', str(byref)], shell=shell)
            if error: sys.exit(error)
            del python, shell, sp

        finally:
            dill._test_file.close()
            try:
                os.remove(session_file % byref)
            except OSError:
                pass

        test_objects(__main__, copy_dict, byref)
        __main__.__dict__.update(copy_dict)
        sys.modules.update(copy_modules)
        del __main__, copy_dict, copy_modules, dump


    # This is for code coverage, tests the use case of dump_session(byref=True)
    # without imported objects in the namespace. It's a contrived example because
    # even dill can't be in it.
    from types import ModuleType
    modname = '__test_main__'
    main = ModuleType(modname)
    main.x = 42

    _main = dill._dill._stash_modules(main)
    if _main is not main:
        print("There are objects to save by referenece that shouldn't be:",
              _main.__dill_imported, _main.__dill_imported_as, _main.__dill_imported_top_level,
              file=sys.stderr)

    test_file = dill._dill.StringIO()
    try:
        dill.dump_session(test_file, main=main, byref=True)
        dump = test_file.getvalue()
        test_file.close()

        sys.modules[modname] = ModuleType(modname)  # empty
        # This should work after fixing https://github.com/uqfoundation/dill/issues/462
        test_file = dill._dill.StringIO(dump)
        dill.load_session(test_file)
    finally:
        test_file.close()

    assert x == 42


    # Dump session for module that is not __main__:
    import test_classdef as module
    atexit.register(_clean_up_cache, module)
    module.selfref = module
    dict_objects = [obj for obj in module.__dict__.keys() if not obj.startswith('__')]

    test_file = dill._dill.StringIO()
    try:
        dill.dump_session(test_file, main=module)
        dump = test_file.getvalue()
        test_file.close()

        for obj in dict_objects:
            del module.__dict__[obj]

        test_file = dill._dill.StringIO(dump)
        dill.load_session(test_file, main=module)
    finally:
        test_file.close()

    assert all(obj in module.__dict__ for obj in dict_objects)
    assert module.selfref is module
