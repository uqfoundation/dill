#!/usr/bin/env python
#
# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""auxiliary internal classes used in multiple submodules, set here to avoid import recursion"""

from __future__ import annotations

__all__ = ['FilterRules', 'Filter', 'RuleType', 'size_filter', '_open']

import contextlib
import math
import random
import re
import warnings
from dataclasses import dataclass, field, fields
from collections import namedtuple
from collections.abc import MutableSet
from enum import Enum
from functools import partialmethod
from itertools import chain, filterfalse
from statistics import mean
from types import ModuleType
from typing import Any, Callable, Dict, Iterable, Pattern, Set, Tuple, Union

from dill import _dill

def _open(filename, mode):
    """return a context manager with an opened file"""
    attr = 'write' if 'w' in mode else 'read'
    if hasattr(filename, attr):
        return contextlib.nullcontext(filename)
    else:
        return open(filename, mode)

def _format_bytes_size(size: Union[int, float]) -> Tuple[int, str]:
    """Return bytes size text representation in human-redable form."""
    unit = "B"
    power_of_2 = math.trunc(size).bit_length() - 1
    magnitude = min(power_of_2 - power_of_2 % 10, 80)  # 2**80 == 1 YiB
    if magnitude:
        size = ((size >> magnitude-1) + 1) >> 1  # rounding trick: 1535 -> 1K; 1536 -> 2K
        unit = "%siB" % "KMGTPEZY"[magnitude // 10]
    return size, unit

# Namespace filtering.

Filter = Union[str, Pattern[str], int, type, Callable]
RuleType = Enum('RuleType', 'EXCLUDE INCLUDE', module=__name__)
Rule = Tuple[RuleType, Union[Filter, Iterable[Filter]]]

class NamedObject:
    """Simple container class for a variable name and value."""
    __slots__ = 'name', 'value'
    def __init__(self, name_value):
        self.name, self.value = name_value
    def __eq__(self, other):
        """
        Prevent simple bugs from writing `lambda obj: obj == 'literal'` instead
        of `lambda obj: obj.value == 'literal' in a filter definition.`
        """
        if type(other) != NamedObject:
            raise TypeError("'==' not supported between instances of 'NamedObject' and %r" %
                    type(other).__name__)
        return super().__eq__(other)

def _iter(filters):
    if isinstance(filters, str):
        return None
    try:
        return iter(filters)
    except TypeError:
        return None

@dataclass
class FilterSet(MutableSet):
    ids: Set[int] = field(default_factory=set)
    names: Set[str] = field(default_factory=set)
    regexes: Set[Pattern[str]] = field(default_factory=set)
    types: Set[type] = field(default_factory=set)
    funcs: Set[Callable] = field(default_factory=set)
    _fields = None
    _rtypemap = None
    _typename_regex = re.compile(r'\w+(?=Type$)|\w+$', re.IGNORECASE)
    def _match_type(self, filter):
        if isinstance(filter, str):
            if filter.isidentifier():
                field = 'names'
            else:
                filter, field = re.compile(filter), 'regexes'
        elif isinstance(filter, re.Pattern):
            field = 'regexes'
        elif isinstance(filter, int):
            field = 'ids'
        elif isinstance(filter, type):
            field = 'types'
        elif callable(filter):
            field = 'funcs'
        else:
            raise ValueError("invalid filter: %r" % filter)
        return filter, getattr(self, field)
    # Mandatory MutableSet methods.
    @classmethod
    def _from_iterable(cls, it):
        obj = cls()
        obj |= it
        return obj
    def __contains__(self, filter):
        filter, filter_set = self._match_type(filter)
        return filter in filter_set
    def __iter__(self):
        return chain.from_iterable(getattr(self, field) for field in self._fields)
    def __len__(self):
        return sum(len(getattr(self, field)) for field in self._fields)
    def add(self, filter):
        filter, filter_set = self._match_type(filter)
        filter_set.add(filter)
    def discard(self, filter):
        filter, filter_set = self._match_type(filter)
        filter_set.discard(filter)
    # Overwrite generic methods (optimization).
    def remove(self, filter):
        filter, filter_set = self._match_type(filter)
        filter_set.remove(filter)
    def clear(self):
        for field in self._fields:
            getattr(self, field).clear()
    def __or__(self, other):
        if not isinstance(other, Iterable):
            return NotImplemented
        obj = self.copy()
        obj |= other
        return obj
    __ror__ = __or__
    def __ior__(self, filters):
        if isinstance(filters, FilterSet):
            for field in self._fields:
                getattr(self, field).update(getattr(filters, field))
        else:
            for filter in filters:
                self.add(filter)
        return self
    # Extra methods.
    def update(self, filters):
        self |= filters
    def copy(self):
        return FilterSet(*(getattr(self, field).copy() for field in self._fields))
    @classmethod
    def _get_typename(cls, key):
        return cls._typename_regex.match(key).group().lower()
    @classmethod
    def get_type(cls, key):
        if cls._rtypemap is None:
            cls._rtypemap = {cls._get_typename(k): v for k, v in _dill._reverse_typemap.items()}
        return cls._rtypemap[cls._get_typename(key)]
    def add_type(self, typename):
        self.types.add(self.get_type(typename))
FilterSet._fields = tuple(field.name for field in fields(FilterSet))

class _FilterSetDescriptor:
    """descriptor for FilterSet members of FilterRules"""
    def __set_name__(self, owner, name):
        self.name = name
        self._name = '_' + name
    def __set__(self, obj, value):
        # This is the important method.
        if isinstance(value, FilterSet):
            setattr(obj, self._name, value)
        else:
            setattr(obj, self._name, FilterSet(value))
    def __get__(self, obj, objtype=None):
        try:
            return getattr(obj, self._name)
        except AttributeError:
            raise AttributeError(self.name) from None
    def __delete__(self, obj):
        try:
            delattr(obj, self._name)
        except AttributeError:
            raise AttributeError(self.name) from None

class FilterRules:
    __slots__ = '_exclude', '_include'
    exclude = _FilterSetDescriptor()
    include = _FilterSetDescriptor()
    def __init__(self, rules: Union[Iterable[Rule], FilterRules] = None):
        self._exclude = FilterSet()
        self._include = FilterSet()
        if rules is not None:
            self.update(rules)
    def __repr__(self):
        desc = ["<FilterRules:"]
        desc += (
            ["{}={!r}".format(x, getattr(self, x)) for x in ('exclude', 'include') if hasattr(self, x)]
            or ["NOT SET"]
        )
        sep = "\n  " if len(desc) > 2 else " "
        return sep.join(desc).replace("set()", "{}") + ">"
    # Proxy add(), discard(), remove() and clear() to FilterSets.
    def __proxy__(self, method, filter, *, rule_type=RuleType.EXCLUDE):
        if not isinstance(rule_type, RuleType):
            raise ValueError("invalid rule type: %r (must be one of %r)" % (rule_type, list(RuleType)))
        filter_set = getattr(self, rule_type.name.lower())
        getattr(filter_set, method)(filter)
    add = partialmethod(__proxy__, 'add')
    discard = partialmethod(__proxy__, 'discard')
    remove = partialmethod(__proxy__, 'remove')
    def clear(self):
        self.exclude.clear()
        self.include.clear()
    def update(self, rules: Union[Iterable[Rule], FilterRules]):
        """Update both FilterSets from a list of (RuleType, Filter) rules."""
        if isinstance(rules, FilterRules):
           for field in FilterSet._fields:
                getattr(self.exclude, field).update(getattr(rules.exclude, field))
                getattr(self.include, field).update(getattr(rules.include, field))
        else:
            for rule in rules:
                # Validate rules.
                if not isinstance(rule, tuple) or len(rule) != 2:
                    raise ValueError("invalid rule format: %r" % rule)
            for rule_type, filter in rules:
                filters = _iter(filter)
                if filters is not None:
                    for f in filters:
                        self.add(f, rule_type=rule_type)
                else:
                    self.add(filter, rule_type=rule_type)

    def _apply_filters(self, filter_set, objects):
        filters = []
        types_list = tuple(filter_set.types)
        # Apply broader/cheaper filters first.
        if types_list:
            filters.append(lambda obj: isinstance(obj.value, types_list))
        if filter_set.ids:
            filters.append(lambda obj: id(obj.value) in filter_set.ids)
        if filter_set.names:
            filters.append(lambda obj: obj.name in filter_set.names)
        if filter_set.regexes:
            filters.append(lambda obj: any(regex.fullmatch(obj.name) for regex in filter_set.regexes))
        filters.extend(filter_set.funcs)
        for filter in filters:
            objects = filterfalse(filter, objects)
        return objects

    def filter_vars(self, namespace: Dict[str, Any]) -> Dict[str, Any]:
        """Apply filters to dictionary with names as keys."""
        if not namespace or not (self.exclude or self.include):
            return namespace
        # Protect agains dict changes during the call.
        namespace_copy = namespace.copy()
        all_objs = [NamedObject(item) for item in namespace_copy.items()]

        if not self.exclude:
            # Treat this rule set as an allowlist.
            exclude_objs = all_objs
        else:
            include_names = {obj.name for obj in self._apply_filters(self.exclude, all_objs)}
            exclude_objs = [obj for obj in all_objs if obj.name not in include_names]
        if self.include and exclude_objs:
            exclude_objs = list(self._apply_filters(self.include, exclude_objs))
        if not exclude_objs:
            return namespace

        if len(exclude_objs) == len(namespace):
            warnings.warn(
                "the exclude/include rules applied have excluded all %d items" % len(all_objs),
                _dill.PicklingWarning,
                stacklevel=2
            )
            return {}
        for obj in exclude_objs:
            del namespace_copy[obj.name]
        return namespace_copy


######################
#  Filter factories  #
######################

import collections
import collections.abc
from sys import getsizeof

class size_filter:
    """Create a filter function with a limit for estimated object size.

    Note: Doesn't work on PyPy. See ``help('``py:func:`sys.getsizeof```)'``
    """
    __slots__ = 'limit', 'recursive'
    # Cover "true" collections from 'builtins', 'collections' and 'collections.abc'.
    COLLECTION_TYPES = (
        list,
        tuple,
        collections.deque,
        collections.UserList,
        collections.abc.Mapping,
        collections.abc.Set,
    )
    MINIMUM_SIZE = getsizeof(None, 16)
    MISSING_SLOT = object()

    def __init__(self, limit: str, recursive: bool = True):
        if _dill.IS_PYPY:
            raise NotImplementedError("size_filter() is not implemented for PyPy")
        self.limit = limit
        if type(limit) != int:
            try:
                self.limit = float(limit)
            except (TypeError, ValueError):
                limit_match = re.fullmatch(r'(\d+)\s*(B|[KMGT]i?B?)', limit, re.IGNORECASE)
                if limit_match:
                    coeff, unit = limit_match.groups()
                    coeff, unit = int(coeff), unit.lower()
                    if unit == 'b':
                        self.limit = coeff
                    else:
                        base = 1024 if unit[1:2] == 'i' else 1000
                        exponent = 'kmgt'.index(unit[0]) + 1
                        self.limit = coeff * base**exponent
            else:
                # Will raise error for Inf and NaN.
                self.limit = math.truc(self.limit)
        if type(self.limit) != int:
            # Everything failed.
            raise ValueError("invalid 'limit' value: %r" % limit)
        elif self.limit < 0:
            raise ValueError("'limit' can't be negative %r" % limit)
        self.recursive = recursive

    def __call__(self, obj: NamedObject) -> bool:
        if self.recursive:
            size = self.estimate_size(obj.value)
        else:
            try:
                size = getsizeof(obj.value)
            except ReferenceError:
                size = self.MINIMUM_SIZE
        return size > self.limit

    def __repr__(self):
        return "size_filter(limit=%r, recursive=%r)" % (
                "%d %s" % _format_bytes_size(self.limit),
                self.recursive,
                )

    @classmethod
    def estimate_size(cls, obj: Any, memo: set = None) -> int:
        if memo is None:
            memo = set()
        obj_id = id(obj)
        if obj_id in memo:
            # Object size already counted.
            return 0
        memo.add(obj_id)
        size = cls.MINIMUM_SIZE
        try:
            if isinstance(obj, ModuleType) and _dill._is_builtin_module(obj):
                # Always saved by reference.
                return cls.MINIMUM_SIZE
            size = getsizeof(obj)
            if hasattr(obj, '__dict__'):
                size += cls.estimate_size(obj.__dict__, memo)
            if hasattr(obj, '__slots__'):
                slots = (getattr(obj, x, cls.MISSING_SLOT) for x in obj.__slots__ if x != '__dict__')
                size += sum(cls.estimate_size(x, memo) for x in slots if x is not cls.MISSING_SLOT)
            if (
                isinstance(obj, str)   # common case shortcut
                or not isinstance(obj, collections.abc.Collection)  # general, single test
                or not isinstance(obj, cls.COLLECTION_TYPES)  # specific, multiple tests
            ):
                return size
            if isinstance(obj, collections.ChainMap):  # collections.Mapping subtype
                size += sum(cls.estimate_size(mapping, memo) for mapping in obj.maps)
            elif len(obj) < 1000:
                if isinstance(obj, collections.abc.Mapping):
                    size += sum(cls.estimate_size(k, memo) + cls.estimate_size(v, memo)
                            for k, v in obj.items())
                else:
                    size += sum(cls.estimate_size(item, memo) for item in obj)
            else:
                # Use random sample for large collections.
                sample = set(random.sample(range(len(obj)), k=100))
                if isinstance(obj, collections.abc.Mapping):
                    samples_sizes = (cls.estimate_size(k, memo) + cls.estimate_size(v, memo)
                            for i, (k, v) in enumerate(obj.items()) if i in sample)
                else:
                    samples_sizes = (cls.estimate_size(item, memo)
                            for i, item in enumerate(obj) if i in sample)
                size += len(obj) * mean(samples_sizes)
        except Exception:
            pass
        return size
