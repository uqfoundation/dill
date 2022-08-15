#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import io
import re
import sys
import textwrap
import warnings
from pickletools import optimize
from types import ModuleType

import dill
from dill.session import ModuleFilters, settings as session_settings
from dill.settings import DEFAULT_SETTINGS

regex = r' +\[dill].+(?=\n +Parameters:$)'
config_demo = re.search(regex, dill.read_settings.__doc__, re.DOTALL | re.MULTILINE).group()
config_demo = textwrap.dedent(config_demo)

def test_read_settings():
    dill.read_settings(io.StringIO(config_demo))

    # dill general settings
    dill_default = DEFAULT_SETTINGS['dill']
    assert dill.settings['recurse'] is dill_default['recurse']  # unchanged
    assert dill.settings['byref'] is (not dill_default['byref'])  # here and below: changed
    assert dill.settings['protocol'] != dill_default['protocol']
    assert dill.settings['protocol'] == dill.HIGHEST_PROTOCOL  # value passed as text

    # session settings (excluding filters)
    session_default = DEFAULT_SETTINGS['dill.session']
    assert session_settings['refimported'] is session_default['refimported']  # unchanged
    assert session_settings['refonfail'] is (not session_default['refonfail'])  # changed

    # session default filters
    filters = session_settings['filters']
    assert type(filters) is dill.session.ModuleFilters
    assert filters._module == 'DEFAULT'
    assert len(filters.exclude) == 8 and len(filters.include) == 2
    assert filters.exclude.regexes == {re.compile(r'_.+')}
    assert io.BytesIO in filters.exclude.types
    for filter in filters.exclude.funcs:  # it's a set, we don't know the order
        if isinstance(filter, dill._utils.size_filter):
            assert filter.limit == 10000
        else:
            obj1 = dill.session.NamedObject(('bool', True))
            obj2 = dill.session.NamedObject(('int', 1))
            assert filter(obj1) is False
            assert filter(obj2) is True
    ## include: different types of filters in the same entry.
    assert len(filters.include.names) == len(filters.include.regexes) == 1

    # module specific filters
    assert filters['some.module']._module == 'some.module'
    assert filters['some.module'].exclude.regexes == filters.exclude.regexes
    assert not hasattr(filters['some.module'], 'include')  # not set, fall back to parent
    ## 'some': parent placeholder
    assert filters['some']._module == 'some'
    assert not hasattr(filters['some'], 'exclude') and not hasattr(filters['some'], 'include')
    ## 'another.module': empty filters, overwrite default filters
    assert len(filters['another.module'].exclude) == len(filters['another.module'].include) == 0

def test_reset_settings():
    dill.reset_settings()
    assert dill.settings == DEFAULT_SETTINGS['dill']
    settings_copy = session_settings.copy()
    del settings_copy['filters']
    assert settings_copy == DEFAULT_SETTINGS['dill.session']
    assert session_settings['filters'] == ModuleFilters(rules=())

class Test:
    def __init__(self):
        pass

def test_settings():
    # byref and recurse
    for option in ('byref', 'recurse'):
        dill.reset_settings()
        NON_DEFAULT = not dill.settings[option]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            pickle1 = dill.dumps(Test)  # default
            pickle2 = dill.dumps(Test, **{option: NON_DEFAULT})
            dill.settings[option] = NON_DEFAULT
            try:
                assert pickle1 != pickle2
                assert dill.dumps(Test) == pickle2
            except AssertionError as error:
                error.args = ("while testing option %r" % option,)
                raise

    # ignore
    dill.reset_settings()
    NON_DEFAULT = not dill.settings['ignore']
    obj = Test()
    copy1 = dill.copy(obj)  # default
    copy2 = dill.copy(obj, ignore=NON_DEFAULT)
    dill.settings['ignore'] = NON_DEFAULT
    copy3 = dill.copy(obj)
    default_res = type(copy1) is Test
    non_default_res = type(copy2) is Test
    assert default_res is not non_default_res
    assert (type(copy3) is Test) is non_default_res

    # protocol
    # Only protocol zero doesn't have an opcode for empty tuple.
    dill.reset_settings()
    EMPTY_TUPLE_0 = b'(t.'
    assert dill.dumps(()) != EMPTY_TUPLE_0
    dill.settings['protocol'] = 0
    assert dill.dumps(()) == EMPTY_TUPLE_0

    # fmode
    dill.reset_settings()
    dill.settings['protocol'] = 0
    for fmode in (dill.HANDLE_FMODE, dill.CONTENTS_FMODE):
        dill.settings['fmode'] = fmode
        dump = optimize(dill.dumps(sys.stdin))  # remove momeize opcodes
        assert dump.endswith(str(fmode).encode() + b'\nV\ntR.')

    # session.refimported
    dill.reset_settings()
    module = ModuleType('__test__')
    module.BUILTIN_CONSTANTS = dill.session.BUILTIN_CONSTANTS
    NON_DEFAULT = not session_settings['refimported']
    ## default
    buf = io.BytesIO()
    dill.dump_module(buf, module)  # refimported=DEFAULT
    buf.seek(0)
    copy1 = dill.load_module(buf)
    ## non-default
    buf = io.BytesIO()
    dill.dump_module(buf, module, refimported=NON_DEFAULT)
    buf.seek(0)
    copy2 = dill.load_module(buf)
    ## non-default (settings)
    session_settings['refimported'] = NON_DEFAULT
    buf = io.BytesIO()
    dill.dump_module(buf, module)
    buf.seek(0)
    copy3 = dill.load_module(buf)
    ## tuple was saved by reference?
    default_res = copy1.BUILTIN_CONSTANTS is dill.session.BUILTIN_CONSTANTS
    non_default_res = copy2.BUILTIN_CONSTANTS is dill.session.BUILTIN_CONSTANTS
    test_res = copy3.BUILTIN_CONSTANTS is dill.session.BUILTIN_CONSTANTS
    assert default_res is not non_default_res
    assert test_res is non_default_res

    # session.refonfail
    dill.reset_settings()
    assert session_settings['refonfail'] is True
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        
        dill.dump_module(io.BytesIO(), sys)  # should work
        session_settings['refonfail'] = False
        try:
            dill.dump_module(io.BytesIO(), sys)
        except Exception:
            pass
        else:
            raise("saving 'sys' without 'refonfail' should have failed")

if __name__ == '__main__':
    test_read_settings()
    test_reset_settings()
    test_settings()
