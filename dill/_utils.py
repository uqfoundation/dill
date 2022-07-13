#!/usr/bin/env python
#
# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""auxiliary internal classes used in multiple submodules, set here to avoid import recursion"""

from __future__ import annotations

__all__ = ['FilterRules', 'Filter', 'RuleType', '_open']

import logging
logger = logging.getLogger('dill._utils')

import contextlib
import re
from dataclasses import dataclass, field, fields
from collections import namedtuple
from collections.abc import MutableSet
from enum import Enum
from functools import partialmethod
from itertools import chain, filterfalse
from types import ModuleType
from typing import Any, Callable, Dict, Iterable, Pattern, Set, Tuple, Union

def _open(filename, mode):
    """return a context manager with an opened file"""
    attr = 'write' if 'w' in mode else 'read'
    if hasattr(filename, attr):
        return contextlib.nullcontext(filename)
    else:
        return open(filename, mode)

# Namespace filtering.

Filter = Union[str, Pattern[str], int, type, Callable]
RuleType = Enum('RuleType', 'EXCLUDE INCLUDE', module=__name__)
Rule = Tuple[RuleType, Union[Filter, Iterable[Filter]]]

NamedObj = namedtuple('NamedObj', 'name value', module=__name__)

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
    def get_type(cls, key):
        if cls._rtypemap is None:
            from ._dill import _reverse_typemap
            cls._rtypemap = {(k[:-4] if k.endswith('Type') else k).lower(): v
                             for k, v in _reverse_typemap.items()}
        if key.endswith('Type'):
            key = key[:-4]
        return cls._rtypemap[key.lower()]
    def add_type(self, type_name):
        self.types.add(self.get_type(type_name))
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

    def filter_vars(self, namespace: Dict[str, Any]):
        """Apply filters to dictionary with names as keys."""
        if not self.exclude and not self.include:
            return namespace

        # Protect agains dict changes during the call.
        namespace_copy = namespace.copy()
        objects = all_objects = [NamedObj._make(item) for item in namespace_copy.items()]

        for filters in (self.exclude, self.include):
            if filters is self.exclude and not filters:
                # Treat the rule set as an allowlist.
                exclude_objs = objects
                continue
            elif filters is self.include:
                if not filters or not exclude_objs:
                    break
                objects = exclude_objs

            flist = []
            types_list = tuple(filters.types)
            # Apply cheaper/broader filters first.
            if types_list:
                flist.append(lambda obj: isinstance(obj.value, types_list))
            if filters.ids:
                flist.append(lambda obj: id(obj.value) in filters.ids)
            if filters.names:
                flist.append(lambda obj: obj.name in filters.names)
            if filters.regexes:
                flist.append(lambda obj: any(regex.fullmatch(obj.name) for regex in filters.regexes))
            flist.extend(filters.funcs)
            for f in flist:
                objects = filterfalse(f, objects)

            if filters is self.exclude:
                include_names = {obj.name for obj in objects}
                exclude_objs = [obj for obj in all_objects if obj.name not in include_names]
            else:
                exclude_objs = list(objects)

        if not exclude_objs:
            return namespace
        if len(exclude_objs) == len(namespace):
            warnings.warn("filtering operation left the namespace empty!", PicklingWarning)
            return {}
        if logger.isEnabledFor(logging.INFO):
            exclude_listing = {obj.name: type(obj.value).__name__ for obj in sorted(exclude_objs)}
            exclude_listing = str(exclude_listing).translate({ord(","): "\n", ord("'"): None})
            logger.info("Objects excluded from dump_session():\n%s\n", exclude_listing)

        for obj in exclude_objs:
            del namespace_copy[obj.name]
        return namespace_copy
