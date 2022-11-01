#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import atexit
import os
import sys
import __main__
from contextlib import suppress
from io import BytesIO
from types import ModuleType

import dill
from dill import _dill

session_file = os.path.join(os.path.dirname(__file__), 'session-refimported-%s.pkl')

###################
#  Child process  #
###################

def _error_line(obj, refimported):
    import traceback
    line = traceback.format_exc().splitlines()[-2].replace('[obj]', '['+repr(obj)+']')
    return "while testing (with refimported=%s):  %s" % (refimported, line.lstrip())

if __name__ == '__main__' and len(sys.argv) >= 3 and sys.argv[1] == '--child':
    # Test session loading in a fresh interpreter session.
    refimported = (sys.argv[2] == 'True')
    dill.load_module(session_file % refimported, module='__main__')

    def test_modules(refimported):
        # FIXME: In this test setting with CPython 3.7, 'calendar' is not included
        # in sys.modules, independent of the value of refimported.  Tried to
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
            if refimported:
                assert __main__.day_name is calendar.day_name

            assert __main__.complex_log is cmath.log

        except AssertionError as error:
            error.args = (_error_line(obj, refimported),)
            raise

    test_modules(refimported)
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
self_dict = __main__.__dict__

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
        with suppress(OSError):
            remove(file)

atexit.register(_clean_up_cache, local_mod)

def _test_objects(main, globals_copy, refimported):
    try:
        main_dict = __main__.__dict__
        global Person, person, Calendar, CalendarSubclass, cal, selfref, self_dict

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
        assert self_dict is __main__.__dict__

    except AssertionError as error:
        error.args = (_error_line(obj, refimported),)
        raise

def test_session_main(refimported):
    """test dump/load_module() for __main__, both in this process and in a subprocess"""
    extra_objects = {}
    if refimported:
        # Test unpickleable imported object in main.
        from sys import flags
        extra_objects['flags'] = flags

    with TestNamespace(**extra_objects) as ns:
        try:
            # Test session loading in a new session.
            dill.dump_module(session_file % refimported, refimported=refimported)
            from dill.tests.__main__ import python, shell, sp
            error = sp.call([python, __file__, '--child', str(refimported)], shell=shell)
            if error: sys.exit(error)
        finally:
            with suppress(OSError):
                os.remove(session_file % refimported)

        # Test session loading in the same session.
        session_buffer = BytesIO()
        dill.dump_module(session_buffer, refimported=refimported)
        session_buffer.seek(0)
        dill.load_module(session_buffer, module='__main__')
        ns.backup['_test_objects'](__main__, ns.backup, refimported)

def test_session_other():
    """test dump/load_module() for a module other than __main__"""
    import test_classdef as module
    atexit.register(_clean_up_cache, module)
    module.selfref = module
    dict_objects = [obj for obj in module.__dict__.keys() if not obj.startswith('__')]

    session_buffer = BytesIO()
    dill.dump_module(session_buffer, module)

    for obj in dict_objects:
        del module.__dict__[obj]

    session_buffer.seek(0)
    dill.load_module(session_buffer, module)

    assert all(obj in module.__dict__ for obj in dict_objects)
    assert module.selfref is module

def test_runtime_module():
    modname = 'runtime'
    runtime_mod = ModuleType(modname)
    runtime_mod.x = 42

    mod, _ = dill.session._stash_modules(runtime_mod, runtime_mod)
    if mod is not runtime_mod:
        print("There are objects to save by referenece that shouldn't be:",
              mod.__dill_imported, mod.__dill_imported_as, mod.__dill_imported_top_level,
              file=sys.stderr)

    # This is also for code coverage, tests the use case of dump_module(refimported=True)
    # without imported objects in the namespace. It's a contrived example because
    # even dill can't be in it.  This should work after fixing #462.
    session_buffer = BytesIO()
    dill.dump_module(session_buffer, module=runtime_mod, refimported=True)
    session_dump = session_buffer.getvalue()

    # Pass a new runtime created module with the same name.
    runtime_mod = ModuleType(modname)  # empty
    return_val = dill.load_module(BytesIO(session_dump), module=runtime_mod)
    assert return_val is None
    assert runtime_mod.__name__ == modname
    assert runtime_mod.x == 42
    assert runtime_mod not in sys.modules.values()

    # Pass nothing as main.  load_module() must create it.
    session_buffer.seek(0)
    runtime_mod = dill.load_module(BytesIO(session_dump))
    assert runtime_mod.__name__ == modname
    assert runtime_mod.x == 42
    assert runtime_mod not in sys.modules.values()

def test_load_module_asdict():
    with TestNamespace():
        session_buffer = BytesIO()
        dill.dump_module(session_buffer)

        global empty, names, x, y
        x = y = 0  # change x and create y
        del empty
        globals_state = globals().copy()

        session_buffer.seek(0)
        main_vars = dill.load_module_asdict(session_buffer)

        assert main_vars is not globals()
        assert globals() == globals_state

        assert main_vars['__name__'] == '__main__'
        assert main_vars['names'] == names
        assert main_vars['names'] is not names
        assert main_vars['x'] != x
        assert 'y' in main_vars
        assert 'empty' in main_vars

    # Test a submodule.
    import html
    from html import entities
    entitydefs = entities.entitydefs

    session_buffer = BytesIO()
    dill.dump_module(session_buffer, entities)
    session_buffer.seek(0)
    entities_vars = dill.load_module_asdict(session_buffer)

    assert entities is html.entities  # restored
    assert entities is sys.modules['html.entities']  # restored
    assert entitydefs is entities.entitydefs  # unchanged
    assert entitydefs is not entities_vars['entitydefs']  # saved by value
    assert entitydefs == entities_vars['entitydefs']

def test_lookup_module():
    assert not _dill._is_builtin_module(local_mod) and local_mod.__package__ == ''

    def lookup(mod, name, obj, lookup_by_name=True):
        from dill._dill import _lookup_module, _module_map
        return _lookup_module(_module_map(mod), name, obj, lookup_by_name)

    name = '__unpickleable'
    obj = object()
    setattr(dill, name, obj)
    assert lookup(dill, name, obj) == (None, None, None)

    # 4th level: non-installed module
    setattr(local_mod, name, obj)
    sys.modules[local_mod.__name__] = sys.modules.pop(local_mod.__name__) # put at the end
    assert lookup(dill, name, obj) == (local_mod.__name__, name, False) # not installed
    try:
        import pox
        # 3rd level: installed third-party module
        setattr(pox, name, obj)
        sys.modules['pox'] = sys.modules.pop('pox')
        assert lookup(dill, name, obj) == ('pox', name, True)
    except ModuleNotFoundError:
        pass
    # 2nd level: module of same package
    setattr(dill.session, name, obj)
    sys.modules['dill.session'] = sys.modules.pop('dill.session')
    assert lookup(dill, name, obj) == ('dill.session', name, True)
    # 1st level: stdlib module
    setattr(os, name, obj)
    sys.modules['os'] = sys.modules.pop('os')
    assert lookup(dill, name, obj) == ('os', name, True)

    # Lookup by id.
    name2 = name + '2'
    setattr(dill, name2, obj)
    assert lookup(dill, name2, obj) == ('os', name, True)
    assert lookup(dill, name2, obj, lookup_by_name=False) == (None, None, None)
    setattr(local_mod, name2, obj)
    assert lookup(dill, name2, obj) == (local_mod.__name__, name2, False)

def test_refimported():
    import collections
    import concurrent.futures
    import types
    import typing

    mod = sys.modules['__test__'] = ModuleType('__test__')
    mod.builtin_module_names = sys.builtin_module_names
    dill.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    mod.Dict = collections.UserDict             # select by type
    mod.AsyncCM = typing.AsyncContextManager    # select by __module__
    mod.thread_exec = dill.executor             # select by __module__ with regex
    mod.local_mod = local_mod

    session_buffer = BytesIO()
    dill.dump_module(session_buffer, mod, refimported=True)
    session_buffer.seek(0)
    mod = dill.load(session_buffer)

    assert mod.__dill_imported == [('sys', 'builtin_module_names')]
    assert set(mod.__dill_imported_as) == {
        ('collections', 'UserDict', 'Dict'),
        ('typing', 'AsyncContextManager', 'AsyncCM'),
        ('dill', 'executor', 'thread_exec'),
    }
    assert mod.__dill_imported_top_level == [(local_mod.__name__, 'local_mod')]

    session_buffer.seek(0)
    dill.load_module(session_buffer, mod)
    del sys.modules['__test__']
    assert mod.builtin_module_names is sys.builtin_module_names
    assert mod.Dict is collections.UserDict
    assert mod.AsyncCM is typing.AsyncContextManager
    assert mod.thread_exec is dill.executor
    assert mod.local_mod is local_mod

def test_unpickleable_var():
    global local_mod
    import keyword as builtin_mod
    from dill._dill import _global_string
    refonfail_default = dill.session.settings['refonfail']
    dill.session.settings['refonfail'] = True
    name = '__unpickleable'
    obj = memoryview(b'')
    assert _dill._is_builtin_module(builtin_mod)
    assert not _dill._is_builtin_module(local_mod)
    # assert not dill.pickles(obj)
    try:
        dill.dumps(obj)
    except _dill.UNPICKLEABLE_ERRORS:
        pass
    else:
        raise Exception("test object should be unpickleable")

    def dump_with_ref(mod, other_mod):
        setattr(other_mod, name, obj)
        buf = BytesIO()
        dill.dump_module(buf, mod)
        return buf.getvalue()

    # "user" modules
    _local_mod = local_mod
    del local_mod  # remove from __main__'s namespace
    try:
        dump_with_ref(__main__, __main__)
    except dill.PicklingError:
        pass  # success
    else:
        raise Exception("saving with a reference to the module itself should fail for '__main__'")
    assert _global_string(_local_mod.__name__, name) in dump_with_ref(__main__, _local_mod)
    assert _global_string('os', name) in dump_with_ref(__main__, os)
    local_mod = _local_mod
    del _local_mod, __main__.__unpickleable, local_mod.__unpickleable, os.__unpickleable

    # "builtin" or "installed" modules
    assert _global_string(builtin_mod.__name__, name) in dump_with_ref(builtin_mod, builtin_mod)
    assert _global_string(builtin_mod.__name__, name) in dump_with_ref(builtin_mod, local_mod)
    assert _global_string('os', name) in dump_with_ref(builtin_mod, os)
    del builtin_mod.__unpickleable, local_mod.__unpickleable, os.__unpickleable

    dill.session.settings['refonfail'] = refonfail_default

if __name__ == '__main__':
    if os.getenv('COVERAGE') != 'true':
        test_session_main(refimported=False)
        test_session_main(refimported=True)
    test_session_other()
    test_runtime_module()
    test_load_module_asdict()
    test_lookup_module()
    test_refimported()
    test_unpickleable_var()
