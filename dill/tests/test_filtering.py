#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import sys

from dill import _dill
from dill._utils import FilterRules, RuleType, size_filter

EXCLUDE = RuleType.EXCLUDE
INCLUDE = RuleType.INCLUDE

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
    if not _dill.IS_PYPY:
        test_size_filter()
