#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import atexit
import os
import sys
import __main__
from io import BytesIO

import dill

session_file = os.path.join(os.path.dirname(__file__), 'session-byref-%s.pkl')

###################
#  Child process  #
###################

def _error_line(error, obj, imported_byref):
    import traceback
    line = traceback.format_exc().splitlines()[-2].replace('[obj]', '['+repr(obj)+']')
    return "while testing (with imported_byref=%s):  %s" % (imported_byref, line.lstrip())

if __name__ == '__main__' and len(sys.argv) >= 3 and sys.argv[1] == '--child':
    # Test session loading in a fresh interpreter session.
    imported_byref = (sys.argv[2] == 'True')
    dill.load_module(session_file % imported_byref)

    def test_modules(imported_byref):
        # FIXME: In this test setting with CPython 3.7, 'calendar' is not included
        # in sys.modules, independent of the value of imported_byref.  Tried to
        # run garbage collection just before loading the session with no luck. It
        # fails even when preceding them with 'import calendar'.  Needed to run
        # these kinds of tests in a supbrocess. Failing test sample:
        #   assert globals()['day_name'] is sys.modules['calendar'].__dict__['day_name']
        try:
            for obj in ('json', 'url', 'local_mod', 'sax', 'dom'):
                assert globals()[obj].__name__ in sys.modules
            assert 'calendar' in sys.modules and 'cmath' in sys.modules
            import calendar, cmath

            for obj in ('Calendar', 'isleap'):
                assert globals()[obj] is sys.modules['calendar'].__dict__[obj]
            assert __main__.day_name.__module__ == 'calendar'
            if imported_byref:
                assert __main__.day_name is calendar.day_name

            assert __main__.complex_log is cmath.log

        except AssertionError as error:
            error.args = (_error_line(error, obj, imported_byref),)
            raise

    test_modules(imported_byref)
    sys.exit()

####################
#  Parent process  #
####################

# Create various kinds of objects to test different internal logics.

## Modules.
import json                                         # top-level module
import urllib as url                                # top-level module under alias
from xml import sax                                 # submodule
import xml.dom.minidom as dom                       # submodule under alias
import test_dictviews as local_mod                  # non-builtin top-level module

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

# Setup global namespace for session saving tests.
class TestNamespace:
    test_globals = globals().copy()
    def __init__(self, **extra):
        self.extra = extra
    def __enter__(self):
        self.backup = globals().copy()
        globals().clear()
        globals().update(self.test_globals)
        globals().update(self.extra)
        return self
    def __exit__(self, *exc_info):
        globals().clear()
        globals().update(self.backup)

def _clean_up_cache(module):
    cached = module.__file__.split('.', 1)[0] + '.pyc'
    cached = module.__cached__ if hasattr(module, '__cached__') else cached
    pycache = os.path.join(os.path.dirname(module.__file__), '__pycache__')
    for remove, file in [(os.remove, cached), (os.removedirs, pycache)]:
        try:
            remove(file)
        except OSError:
            pass

atexit.register(_clean_up_cache, local_mod)

def _test_objects(main, globals_copy, imported_byref):
    try:
        main_dict = __main__.__dict__
        global Person, person, Calendar, CalendarSubclass, cal, selfref

        for obj in ('json', 'url', 'local_mod', 'sax', 'dom'):
            assert globals()[obj].__name__ == globals_copy[obj].__name__

        for obj in ('x', 'empty', 'names'):
            assert main_dict[obj] == globals_copy[obj]

        for obj in ['squared', 'cubed']:
            assert main_dict[obj].__globals__ is main_dict
            assert main_dict[obj](3) == globals_copy[obj](3)

        assert Person.__module__ == __main__.__name__
        assert isinstance(person, Person)
        assert person.age == globals_copy['person'].age

        assert issubclass(CalendarSubclass, Calendar)
        assert isinstance(cal, CalendarSubclass)
        assert cal.weekdays() == globals_copy['cal'].weekdays()

        assert selfref is __main__

    except AssertionError as error:
        error.args = (_error_line(error, obj, imported_byref),)
        raise

def test_session_main(imported_byref):
    """test dump/load_module() for __main__, both in this process and in a subprocess"""
    extra_objects = {}
    if imported_byref:
        # Test unpickleable imported object in main.
        from sys import flags
        extra_objects['flags'] = flags

    with TestNamespace(**extra_objects) as ns:
        try:
            # Test session loading in a new session.
            dill.dump_module(session_file % imported_byref, imported_byref=imported_byref)
            from dill.tests.__main__ import python, shell, sp
            error = sp.call([python, __file__, '--child', str(imported_byref)], shell=shell)
            if error: sys.exit(error)
        finally:
            try:
                os.remove(session_file % imported_byref)
            except OSError:
                pass

        # Test session loading in the same session.
        session_buffer = BytesIO()
        dill.dump_module(session_buffer, imported_byref=imported_byref)
        session_buffer.seek(0)
        dill.load_module(session_buffer)
        ns.backup['_test_objects'](__main__, ns.backup, imported_byref)

def test_session_other():
    """test dump/load_module() for a module other than __main__"""
    import test_classdef as module
    atexit.register(_clean_up_cache, module)
    module.selfref = module
    dict_objects = [obj for obj in module.__dict__.keys() if not obj.startswith('__')]

    session_buffer = BytesIO()
    dill.dump_module(session_buffer, main=module)

    for obj in dict_objects:
        del module.__dict__[obj]

    session_buffer.seek(0)
    dill.load_module(session_buffer) #, main=module)

    assert all(obj in module.__dict__ for obj in dict_objects)
    assert module.selfref is module

def test_runtime_module():
    from types import ModuleType
    modname = '__runtime__'
    runtime = ModuleType(modname)
    runtime.x = 42

    mod = dill._dill._stash_modules(runtime)
    if mod is not runtime:
        print("There are objects to save by referenece that shouldn't be:",
              mod.__dill_imported, mod.__dill_imported_as, mod.__dill_imported_top_level,
              file=sys.stderr)

    # This is also for code coverage, tests the use case of dump_module(imported_byref=True)
    # without imported objects in the namespace. It's a contrived example because
    # even dill can't be in it.  This should work after fixing #462.
    session_buffer = BytesIO()
    dill.dump_module(session_buffer, main=runtime, imported_byref=True)
    session_dump = session_buffer.getvalue()

    # Pass a new runtime created module with the same name.
    runtime = ModuleType(modname)  # empty
    returned_mod = dill.load_module(BytesIO(session_dump), main=runtime)
    assert returned_mod is runtime
    assert runtime.__name__ == modname
    assert runtime.x == 42
    assert runtime not in sys.modules.values()

    # Pass nothing as main.  load_module() must create it.
    session_buffer.seek(0)
    runtime = dill.load_module(BytesIO(session_dump))
    assert runtime.__name__ == modname
    assert runtime.x == 42
    assert runtime not in sys.modules.values()

def test_load_module_vars():
    with TestNamespace():
        session_buffer = BytesIO()
        dill.dump_module(session_buffer)

        global empty, names, x, y
        x = y = 0  # change x and create y
        del empty
        globals_state = globals().copy()

        session_buffer.seek(0)
        main_vars = dill.load_module_vars(session_buffer)

        assert main_vars is not globals()
        assert globals() == globals_state

        assert main_vars['__name__'] == '__main__'
        assert main_vars['names'] == names
        assert main_vars['names'] is not names
        assert main_vars['x'] != x
        assert 'y' not in main_vars
        assert 'empty' in main_vars

if __name__ == '__main__':
    test_session_main(imported_byref=False)
    test_session_main(imported_byref=True)
    test_session_other()
    test_runtime_module()
    test_load_module_vars()
