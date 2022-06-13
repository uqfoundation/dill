#!/usr/bin/env python
#
# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""auxiliary internal classes used in multiple submodules, set here to avoid import recursion"""

__all__ = ['AttrDict', 'ExcludeRules', 'Filter', 'RuleType']

import logging
logger = logging.getLogger('dill._utils')

class AttrDict(dict):
    """syntactic sugar for accessing dictionary items"""
    def _check_attr(self, name):
        try:
            super().__getattribute__(name)
        except AttributeError:
            pass
        else:
            raise AttributeError("'AttrDict' object attribute %r is read-only" % name)
    def __getattr__(self, key):
        # This is called only if dict.__getattribute__(key) fails.
        try:
            return self[key]
        except KeyError:
            raise AttributeError("'AttrDict' object has no attribute %r" % key)
    def __setattr__(self, key, value):
        self._check_attr(key)
        self[key] = value
    def __delattr__(self, key):
        self._check_attr(key)
        del self[key]
    def __reduce__(self):
        return type(self), (dict(self),)


### Namespace filtering
import re
from dataclasses import InitVar, dataclass, field, fields
from collections import abc, namedtuple
from enum import Enum
from functools import partialmethod
from itertools import filterfalse
from typing import Callable, Iterable, Pattern, Set, Tuple, Union

RuleType = Enum('RuleType', 'EXCLUDE INCLUDE', module=__name__)
NamedObj = namedtuple('NamedObj', 'name value', module=__name__)

Filter = Union[str, Pattern[str], int, type, Callable]
Rule = Tuple[RuleType, Union[Filter, Iterable[Filter]]]

def isiterable(arg):
    return isinstance(arg, abc.Iterable) and not isinstance(arg, (str, bytes))

@dataclass
class ExcludeFilters:
    ids: Set[int] = field(default_factory=set)
    names: Set[str] = field(default_factory=set)
    regex: Set[Pattern[str]] = field(default_factory=set)
    types: Set[type] = field(default_factory=set)
    funcs: Set[Callable] = field(default_factory=set)

    @property
    def filter_sets(self):
        return tuple(field.name for field in fields(self))
    def __bool__(self):
        return any(getattr(self, filter_set) for filter_set in self.filter_sets)
    def _check(self, filter):
        if isinstance(filter, str):
            if filter.isidentifier():
                field = 'names'
            else:
                filter, field = re.compile(filter), 'regex'
        elif isinstance(filter, re.Pattern):
            field = 'regex'
        elif isinstance(filter, int):
            field = 'ids'
        elif isinstance(filter, type):
            field = 'types'
        elif callable(filter):
            field = 'funcs'
        else:
            raise ValueError("invalid filter: %r" % filter)
        return filter, getattr(self, field)
    def add(self, filter):
        filter, filter_set = self._check(filter)
        filter_set.add(filter)
    def discard(self, filter):
        filter, filter_set = self._check(filter)
        filter_set.discard(filter)
    def remove(self, filter):
        filter, filter_set = self._check(filter)
        filter_set.remove(filter)
    def update(self, filters):
        for filter in filters:
            self.add(filter)
    def clear(self):
        for filter_set in self.filter_sets:
            getattr(self, filter_set).clear()
    def add_type(self, type_name):
        import types
        name_suffix = type_name + 'Type' if not type_name.endswith('Type') else type_name
        if hasattr(types, name_suffix):
            type_name = name_suffix
        type_obj = getattr(types, type_name, None)
        if not isinstance(type_obj, type):
            named = type_name if type_name == name_suffix else "%r or %r" % (type_name, name_suffix)
            raise NameError("could not find a type named %s in module 'types'" % named)
        self.types.add(type_obj)

@dataclass
class ExcludeRules:
    exclude: ExcludeFilters = field(init=False, default_factory=ExcludeFilters)
    include: ExcludeFilters = field(init=False, default_factory=ExcludeFilters)
    rules: InitVar[Iterable[Rule]] = None

    def __post_init__(self, rules):
        if rules is not None:
            self.update(rules)

    def __proxy__(self, method, filter, *, rule_type=RuleType.EXCLUDE):
        if rule_type is RuleType.EXCLUDE:
            getattr(self.exclude, method)(filter)
        elif rule_type is RuleType.INCLUDE:
            getattr(self.include, method)(filter)
        else:
            raise ValueError("invalid rule type: %r (must be one of %r)" % (rule_type, list(RuleType)))

    add = partialmethod(__proxy__, 'add')
    discard = partialmethod(__proxy__, 'discard')
    remove = partialmethod(__proxy__, 'remove')

    def update(self, rules):
        if isinstance(rules, ExcludeRules):
           for filter_set in self.exclude.filter_sets:
                getattr(self.exclude, filter_set).update(getattr(rules.exclude, filter_set))
                getattr(self.include, filter_set).update(getattr(rules.include, filter_set))
        else:
            # Validate rules.
            for rule in rules:
                if not isinstance(rule, tuple) or len(rule) != 2:
                    raise ValueError("invalid rule format: %r" % rule)
            for rule_type, filter in rules:
                if isiterable(filter):
                    for f in filter:
                        self.add(f, rule_type=rule_type)
                else:
                    self.add(filter, rule_type=rule_type)

    def clear(self):
        self.exclude.clear()
        self.include.clear()

    def filter_namespace(self, namespace, obj=None):
        if not self.exclude and not self.include:
            return namespace

        # Protect agains dict changes during the call.
        namespace_copy = namespace.copy() if obj is None or namespace is vars(obj) else namespace
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
            if filters.regex:
                flist.append(lambda obj: any(regex.fullmatch(obj.name) for regex in filters.regex))
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
