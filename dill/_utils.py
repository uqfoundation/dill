#!/usr/bin/env python
#
# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
Auxiliary classes and functions used in more than one module, defined here to
avoid circular import problems.
"""

from __future__ import annotations

__all__ = ['FilterRules', 'Filter', 'RuleType', 'size_filter', 'EXCLUDE', 'INCLUDE']

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

RuleType = Enum('RuleType', 'EXCLUDE INCLUDE', module=__name__)
EXCLUDE, INCLUDE = RuleType.EXCLUDE, RuleType.INCLUDE

Filter = Union[str, Pattern[str], int, type, Callable]
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
    """A superset of exclude/include filter sets."""
    names: Set[str] = field(default_factory=set)
    regexes: Set[Pattern[str]] = field(default_factory=set)
    ids: Set[int] = field(default_factory=set)
    types: Set[type] = field(default_factory=set)
    funcs: Set[Callable] = field(default_factory=set)
    _fields = None
    _rtypemap = None
    _typename_regex = re.compile(r'\w+(?=Type$)|\w+$', re.IGNORECASE)
    def _match_type(self, filter):
        filter_type = type_filter
        if filter_type == str:
            if filter.isidentifier():
                field = 'names'
            else:
                filter, field = re.compile(filter), 'regexes'
        elif filter_type == re.Pattern:
            field = 'regexes'
        elif filter_type == int:
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
    def add_type(self, typename: str) -> None:
        """Add a type filter to the set by passsing the type name.

        Parameters:
            typename: a type name (case insensitive).

        Example:
            Add some type filters to default exclusion filters:

            >>> import dill
            >>> filters = dill.settings['dump_module']['filters']
            >>> filters.exclude.add_type('type')
            >>> filters.exclude.add_type('Function')
            >>> filters.exclude.add_type('ModuleType')
            >>> filters
            <ModuleFilters DEFAULT:
              exclude=FilterSet(types={<class 'type'>, <class 'module'>, <class 'function'>}),
              include=FilterSet()>
        """
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
    """Exclude and include rules for filtering a namespace.

    Namespace filtering rules can be of two types, ``EXCLUDE`` and ``INCLUDE``
    rules, and of five "flavors":

        - `name`: match a variable name exactly;
        - `regex`: match a variable name by regular expression;
        - `id`: match a variable value by id;
        - `type`: match a variable value by type (using ``isinstance``);
        - `func`: callable filter, match a variable name and/or value by an
          arbitrary logic.

    A `name` filter is specified by a simple string, e.g. 'some_var'. If its
    value is not a valid Python identifier, it is treated as a regular
    expression instead.

    A `regex` filter is specified either by a string containing a regular
    expression, e.g. ``r'\w+_\d+'``, or by a :py:class:`re.Pattern` object.

    An `id` filter is specified by an ``int`` that corresponds to the id of an
    object. For example, to exclude a specific object ``obj`` that may me
    assigned to multiple variables, just use ``id(obj)`` as an `id` filter.

    A `type` filter is specified by a type-object, e.g. ``list`` or
    ``type(some_var)``.  For adding `type` filters by the type name, see
    :py:func:`FilterSet.add_type`.

    A `func` filter can be any callable that accepts a single argument and
    returns a boolean value, being it ``True`` if the object should be excluded
    (or included) or ``False`` if it should *not* be excluded (or included).
    The single argument is an object with two attributes: ``name`` is the
    variable's name in the namespace and ``value`` is the object that it refers
    to.  Below are some examples of `func` filters.

    Exclude objects that were renamed after definition:

    >>> renamed_filter = lambda obj: obj.name != getattr(obj.value, '__name__', obj.name)

    Strict type filter, exclude ``int`` but not ``bool`` (an ``int`` subclass):

    >>> int_filter = lambda obj: type(obj) == int

    Filters may be added interactively after creating an empty ``FilterRules``
    object:

    >>> from dill.session import FilterRules
    >>> filters = FilterRules()
    >>> filters.exclude.add('some_var')
    >>> filters.exclude.add(r'__\w+')
    >>> filters.include.add(r'__\w+__') # keep __dunder__ variables

    Or may be created all at once at initialization with "filter rule literals":

    >>> from dill.session import FilterRules, EXCLUDE, INCLUDE
    >>> filters = FilterRules([
    ...     (EXCLUDE, ['some_var', r'__\+']),
    ...     (INCLUDE, r'__\w+__'),
    ... ])

    The order that the exclude and include filters are added is irrelevant
    because **exclude filters are always applied first**.  Therefore, generally
    the rules work as a blocklist, with include filters acting as exceptions to
    the exclusion rules.  However, **if there are only include filters, the
    rules work as an allowlist** instead, and only the variables matched by the
    include filters are kept.
    """
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
        for attr in ('exclude', 'include'):
            set_desc = getattr(self, attr, None)
            if set_desc is None:
                continue
            set_desc = repr(set_desc)
            set_desc = re.sub(r'(\w+=set\(\)(, )?)', '', set_desc).replace(', )', ')')
            if len(set_desc) > 78:
                set_desc = ["FilterSet("] + re.findall(r'\w+={.+?}', set_desc)
                set_desc = ",\n    ".join(set_desc) + "\n  )"
            set_desc = "%s=%s" % (attr, set_desc)
            if attr == 'exclude' and hasattr(self, 'include'):
                set_desc += ','
            desc.append(set_desc)
        if len(desc) == 1:
            desc += ["NOT SET"]
        sep = "\n  " if sum(len(x) for x in desc) > 78 else " "
        return sep.join(desc) + ">"
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

    Parameters:
        limit: maximum size allowed in bytes. May be an absolute number of bytes
          as an ``int`` or ``float``, or a string representing a size in bytes,
          e.g. ``1000``, ``10e3``, ``"1000"``, ``"1k"`` and ``"1 KiB"`` are all
          valid and roughly equivalent (the last one represents 1024 bytes).
        recursive: if `False`, the function won't recurse into the object's
          attributes and items to estimate its size.

    Returns:
        A callable filter to be used with :py:func:`dump_module`.

    Note:
        Doesn't work on PyPy. See ``help(sys.getsizeof)``.
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

    def __init__(self,
        limit: Union[int, float, str],
        recursive: bool = True,
    ) -> Callable[NamedObject, bool]:
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
