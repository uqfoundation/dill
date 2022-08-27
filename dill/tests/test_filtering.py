#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import sys
from types import ModuleType

import dill
from dill import _dill
from dill.session import (
    EXCLUDE, INCLUDE, FilterRules, RuleType, ipython_filter, size_filter, settings
)

NS = {
    'a': 1,
    'aa': 2,
    'aaa': 3,
    'b': 42,
    'bazaar': 'cathedral',
    'has_spam': True,
    'Integer': int,
}

def did_exclude(namespace, rules, excluded_subset):
    rules = FilterRules(rules)
    filtered = rules.apply_filters(namespace)
    return set(namespace).difference(filtered) == excluded_subset

def test_basic_filtering():
    filter_names = [(EXCLUDE, ['a', 'c'])]  # not 'aa', etc.
    assert did_exclude(NS, filter_names, excluded_subset={'a'})

    filter_regexes = [(EXCLUDE, [r'aa+', r'bb+'])]  # not 'a', 'b', 'bazaar'
    assert did_exclude(NS, filter_regexes, excluded_subset={'aa', 'aaa'})

    # Should exclude 'b' and 'd', and not 'b_id'.
    NS_copy = NS.copy()
    NS_copy['d'] = NS['b']
    NS_copy['b_id'] = id(NS['b'])
    filter_ids = [(EXCLUDE, id(NS['b']))]
    assert did_exclude(NS_copy, filter_ids, excluded_subset={'b', 'd'})

    # Should also exclude bool 'has_spam' (int subclass).
    filter_types = [(EXCLUDE, [int, frozenset])]
    assert did_exclude(NS, filter_types, excluded_subset={'a', 'aa', 'aaa', 'b', 'has_spam'})

    # Match substring (regexes use fullmatch()).
    filter_funcs_name = [(EXCLUDE, lambda obj: 'aa' in obj.name)]
    assert did_exclude(NS, filter_funcs_name, excluded_subset={'aa', 'aaa', 'bazaar'})

    # Don't exclude subclasses.
    filter_funcs_value = [(EXCLUDE, lambda obj: type(obj.value) == int)]
    assert did_exclude(NS, filter_funcs_value, excluded_subset={'a', 'aa', 'aaa', 'b'})

def test_exclude_include():
    # Include rules must apply after exclude rules.
    filter_include = [(EXCLUDE, r'a+'), (INCLUDE, 'aa')]  # not 'aa'
    assert did_exclude(NS, filter_include, excluded_subset={'a', 'aaa'})

    # If no exclude rules, behave as an allowlist.
    filter_allowlist = [(INCLUDE, lambda obj: 'a' in obj.name)]
    assert did_exclude(NS, filter_allowlist, excluded_subset={'b', 'Integer'})

def test_add_type():
    type_rules = FilterRules()                 # Formats accepted (actually case insensitive):
    type_rules.exclude.add('type: function')   # 1. typename
    type_rules.exclude.add('type:  Type  ')    # 2. Typename
    type_rules.exclude.add('type:ModuleType')  # 2. TypenameType
    NS_copy = NS.copy()
    NS_copy.update(F=test_basic_filtering, T=FilterRules, M=_dill)
    assert did_exclude(NS_copy, type_rules, excluded_subset={'F', 'T', 'M', 'Integer'})

def test_module_filters():
    R"""Test filters specific for a module and fallback to parent module or default.

    The settings['filers'] single-branched tree structure in these tests:

    exclude:      {r'_.*[^_]'}    None            None
                 /               /               /
                *-------------* *-------------* *-------------* *~~~~~~~~~~~~~*
    module:     |   DEFAULT   |-|     foo*    |-|   foo.bar   | | foo.bar.baz |
                *-------------* *-------------* *-------------* *~~~~~~~~~~~~~*
                 \               \               \               \_____ _____/
    include:      {'_keep'}       None            {} (empty)           V
                                                                    missing
    (*) 'foo' is a placeholder node
    """
    import io
    foo = sys.modules['foo'] = ModuleType('foo')
    foo.bar = sys.modules['foo.bar'] = ModuleType('foo.bar')
    foo.bar.baz = sys.modules['foo.bar.baz'] = ModuleType('foo.bar.baz')
    NS = {'_filter': 1, '_keep': 2}

    def _dump_load_dict(module):
        module.__dict__.update(NS)
        buf = io.BytesIO()
        dill.dump_module(buf, module)
        for var in NS:
            delattr(module, var)
        buf.seek(0)
        return dill.load_module_asdict(buf)

    # Empty default filters
    filters = settings['filters']
    saved = _dump_load_dict(foo)
    assert '_filter' in saved
    assert '_keep' in saved

    # Default filters
    filters.exclude.add(r'_.*[^_]')
    filters.include.add('_keep')
    assert filters.get_rules('foo') is filters
    saved = _dump_load_dict(foo)
    assert '_filter' not in saved
    assert '_keep' in saved

    # Add filters to 'foo.bar' and placeholder node for 'foo'
    filters['foo.bar'] = ()
    del filters.foo.bar.exclude # remove empty exclude filters, fall back to default
    assert not hasattr(filters.foo, 'exclude') and not hasattr(filters.foo, 'include')
    assert not hasattr(filters.foo.bar, 'exclude') and hasattr(filters.foo.bar, 'include')

    # foo: placeholder node falling back to default
    assert filters.foo.get_filters(EXCLUDE) is filters.exclude
    saved = _dump_load_dict(foo)
    assert '_filter' not in saved
    assert '_keep' in saved

    # foo.bar: without exclude rules, with (empty) include rules
    assert filters.foo.bar.get_filters(EXCLUDE) is filters.exclude
    assert filters.foo.bar.get_filters(INCLUDE) is filters.foo.bar.include
    saved = _dump_load_dict(foo.bar)
    assert '_filter' not in saved
    assert '_keep' not in saved

    # foo.bar.baz: without specific filters, falling back to foo.bar
    assert filters.get_rules('foo.bar.baz') is filters.foo.bar
    saved = _dump_load_dict(foo.bar.baz)
    assert '_filter' not in saved
    assert '_keep' not in saved

def test_ipython_filter():
    from itertools import filterfalse
    from types import SimpleNamespace
    _dill.IS_IPYTHON = True  # trick ipython_filter
    sys.modules['IPython'] = MockIPython = ModuleType('IPython')

    # Mimic the behavior of IPython namespaces at __main__.
    user_ns_actual = {'user_var': 1, 'x': 2}
    user_ns_hidden = {'x': 3, '_i1': '1 / 2', '_1': 0.5, 'hidden': 4}
    user_ns = user_ns_hidden.copy()  # user_ns == vars(__main__)
    user_ns.update(user_ns_actual)
    assert user_ns['x'] == user_ns_actual['x']  # user_ns.x masks user_ns_hidden.x
    MockIPython.get_ipython = lambda: SimpleNamespace(user_ns=user_ns, user_ns_hidden=user_ns_hidden)

    # Test variations of keeping or dropping the interpreter history.
    user_vars = set(user_ns_actual)
    def namespace_matches(keep_history, should_keep_vars):
        rules = FilterRules([(EXCLUDE, ipython_filter(keep_history=keep_history))])
        return set(rules.apply_filters(user_ns)) == user_vars | should_keep_vars
    assert namespace_matches(keep_history='input', should_keep_vars={'_i1'})
    assert namespace_matches(keep_history='output', should_keep_vars={'_1'})
    assert namespace_matches(keep_history='both', should_keep_vars={'_i1', '_1'})
    assert namespace_matches(keep_history='none', should_keep_vars=set())

def test_size_filter():
    from sys import getsizeof
    estimate = size_filter.estimate_size

    small = list(range(100))
    large = list(range(1000))
    reflarge = 10*[small]
    small_size = getsizeof(small) + 100*getsizeof(0)
    large_size = getsizeof(large) + 1000*getsizeof(0)
    assert small_size <= estimate(small) < estimate(reflarge) < large_size <= estimate(large)

    NS_copy = NS.copy()  # all base objects are small and should not be excluded
    reflarge.append(reflarge)  # recursive reference
    NS_copy.update(small=small, large=large, reflarge=reflarge)
    filter_size = [(EXCLUDE, size_filter(limit=5*small_size))]
    assert did_exclude(NS_copy, filter_size, excluded_subset={'large'})

if __name__ == '__main__':
    test_basic_filtering()
    test_exclude_include()
    test_add_type()
    test_module_filters()
    test_ipython_filter()
    if not _dill.IS_PYPY:
        test_size_filter()
