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

__all__ = [
    'Filter', 'FilterFunction', 'FilterRules', 'FilterSet', 'NamedObject',
    'Rule', 'RuleType', 'size_filter', 'EXCLUDE', 'INCLUDE',
]

import contextlib
import io
import math
import re
import warnings
from dataclasses import dataclass, field, fields
from collections import abc
from contextlib import suppress
from enum import Enum
from functools import partialmethod
from itertools import chain, filterfalse

from dill import _dill  # _dill is not completely loaded

# Type hints.
from typing import (
    Any, Callable, Dict, Iterable, Iterator,
    Optional, Pattern, Set, Tuple, Union,
)

def _format_bytes_size(size: Union[int, float]) -> Tuple[int, str]:
    """Return bytes size text representation in human-redable form."""
    unit = "B"
    power_of_2 = math.trunc(size).bit_length() - 1
    magnitude = min(power_of_2 - power_of_2 % 10, 80)  # 2**80 == 1 YiB
    if magnitude:
        # Rounding trick: 1535 (1024 + 511) -> 1K; 1536 -> 2K
        size = ((size >> magnitude-1) + 1) >> 1
        unit = "%siB" % "KMGTPEZY"[(magnitude // 10) - 1]
    return size, unit


## File-related utilities ##

class _PeekableReader(contextlib.AbstractContextManager):
    """lightweight readable stream wrapper that implements peek()"""
    def __init__(self, stream, closing=True):
        self.stream = stream
        self.closing = closing
    def __exit__(self, *exc_info):
        if self.closing:
            self.stream.close()
    def read(self, n):
        return self.stream.read(n)
    def readline(self):
        return self.stream.readline()
    def tell(self):
        return self.stream.tell()
    def close(self):
        return self.stream.close()
    def peek(self, n):
        stream = self.stream
        try:
            if hasattr(stream, 'flush'):
                stream.flush()
            position = stream.tell()
            stream.seek(position)  # assert seek() works before reading
            chunk = stream.read(n)
            stream.seek(position)
            return chunk
        except (AttributeError, OSError):
            raise NotImplementedError("stream is not peekable: %r", stream) from None

class _SeekableWriter(io.BytesIO, contextlib.AbstractContextManager):
    """works as an unlimited buffer, writes to file on close"""
    def __init__(self, stream, closing=True, *args, **kwds):
        super().__init__(*args, **kwds)
        self.stream = stream
        self.closing = closing
    def __exit__(self, *exc_info):
        self.close()
    def close(self):
        self.stream.write(self.getvalue())
        with suppress(AttributeError):
            self.stream.flush()
        super().close()
        if self.closing:
            self.stream.close()

def _open(file, mode, *, peekable=False, seekable=False):
    """return a context manager with an opened file-like object"""
    readonly = ('r' in mode and '+' not in mode)
    if not readonly and peekable:
        raise ValueError("the 'peekable' option is invalid for writable files")
    if readonly and seekable:
        raise ValueError("the 'seekable' option is invalid for read-only files")
    should_close = not hasattr(file, 'read' if readonly else 'write')
    if should_close:
        file = open(file, mode)
    # Wrap stream in a helper class if necessary.
    if peekable and not hasattr(file, 'peek'):
        # Try our best to return it as an object with a peek() method.
        if hasattr(file, 'seekable'):
            file_seekable = file.seekable()
        elif hasattr(file, 'seek') and hasattr(file, 'tell'):
            try:
                file.seek(file.tell())
                file_seekable = True
            except Exception:
                file_seekable = False
        else:
            file_seekable = False
        if file_seekable:
            file = _PeekableReader(file, closing=should_close)
        else:
            try:
                file = io.BufferedReader(file)
            except Exception:
                # It won't be peekable, but will fail gracefully in _identify_module().
                file = _PeekableReader(file, closing=should_close)
    elif seekable and (
        not hasattr(file, 'seek')
        or not hasattr(file, 'truncate')
        or (hasattr(file, 'seekable') and not file.seekable())
    ):
        file = _SeekableWriter(file, closing=should_close)
    if should_close or isinstance(file, (_PeekableReader, _SeekableWriter)):
        return file
    else:
        return contextlib.nullcontext(file)


## Namespace filtering ##

RuleType = Enum('RuleType', 'EXCLUDE INCLUDE', module=__name__)
EXCLUDE, INCLUDE = RuleType.EXCLUDE, RuleType.INCLUDE

class NamedObject:
    """Simple container for a variable's name and value used by filter functions."""
    __slots__ = 'name', 'value'
    name: str
    value: Any
    def __init__(self, name_value: Tuple[str, Any]):
        self.name, self.value = name_value
    def __eq__(self, other: Any) -> bool:
        """
        Prevent simple bugs from writing `lambda obj: obj == 'literal'` instead
        of `lambda obj: obj.value == 'literal' in a filter definition.`
        """
        if type(other) is not NamedObject:
            raise TypeError("'==' not supported between instances of 'NamedObject' and %r" %
                    type(other).__name__)
        return self.value is other.value and self.name == other.name
    def __repr__(self):
        return "NamedObject(%r, %r)" % (self.name, self.value)

FilterFunction = Callable[[NamedObject], bool]
Filter = Union[str, Pattern[str], int, type, FilterFunction]
Rule = Tuple[RuleType, Union[Filter, Iterable[Filter]]]

def _iter(obj):
    """return iterator of object if it's not a string"""
    if isinstance(obj, (str, bytes)):
        return None
    try:
        return iter(obj)
    except TypeError:
        return None

@dataclass
class FilterSet(abc.MutableSet):
    """A superset of exclusion/inclusion filter sets."""
    names: Set[str] = field(default_factory=set)
    regexes: Set[Pattern[str]] = field(default_factory=set)
    ids: Set[int] = field(default_factory=set)
    types: Set[type] = field(default_factory=set)
    funcs: Set[FilterFunction] = field(default_factory=set)

    # Initialized later.
    _fields = None
    _rtypemap = None

    def _match_type(self, filter: Filter) -> Tuple[filter, str]:
        """identify the filter's type and convert it to standard internal format"""
        filter_type = type(filter)
        if filter_type is str:
            if filter.isidentifier():
                field = 'names'
            elif filter.startswith('type:'):
                filter = self.get_type(filter.partition(':')[-1].strip())
                field = 'types'
            else:
                filter = re.compile(filter)
                field = 'regexes'
        elif filter_type is re.Pattern and type(filter.pattern) is str:
            field = 'regexes'
        elif filter_type is int:
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
    def _from_iterable(cls, it: Iterable[Filter]) -> FilterSet:
        obj = cls()
        obj |= it
        return obj
    def __bool__(self) -> bool:
        return any(getattr(self, field) for field in self._fields)
    def __len__(self) -> int:
        return sum(len(getattr(self, field)) for field in self._fields)
    def __contains__(self, filter: Filter) -> bool:
        filter, filter_set = self._match_type(filter)
        return filter in filter_set
    def __iter__(self) -> Iterator[Filter]:
        return chain.from_iterable(getattr(self, field) for field in self._fields)
    def add(self, filter: Filter) -> None:
        filter, filter_set = self._match_type(filter)
        filter_set.add(filter)
    def discard(self, filter: Filter) -> None:
        filter, filter_set = self._match_type(filter)
        filter_set.discard(filter)

    # Overwrite generic methods (optimization).
    def remove(self, filter: Filter) -> None:
        filter, filter_set = self._match_type(filter)
        filter_set.remove(filter)
    def clear(self) -> None:
        for field in self._fields:
            getattr(self, field).clear()
    def __or__(self, other: Iterable[Filter]) -> FilterSet:
        obj = self.copy()
        obj |= other
        return obj
    __ror__ = __or__
    def __ior__(self, other: Iterable[Filter]) -> FilterSet:
        if not isinstance(other, Iterable):
            return NotImplemented
        if isinstance(other, FilterSet):
            for field in self._fields:
                getattr(self, field).update(getattr(other, field))
        else:
            for filter in other:
                self.add(filter)
        return self

    # Extra methods.
    def update(self, filters: Iterable[Filters]) -> None:
        self |= filters
    def copy(self) -> FilterSet:
        return FilterSet(*(getattr(self, field).copy() for field in self._fields))

    # Convert type name to type.
    TYPENAME_REGEX = re.compile(r'\w+(?=Type$)|\w+$', re.IGNORECASE)
    @classmethod
    def _get_typekey(cls, typename: str) -> str:
        return cls.TYPENAME_REGEX.match(typename).group().lower()
    @classmethod
    def get_type(cls, typename: str) -> type:
        """retrieve a type registered in ``dill``'s "reverse typemap"'"""
        if cls._rtypemap is None:
            cls._rtypemap = {cls._get_typekey(k): v for k, v in _dill._reverse_typemap.items()}
        return cls._rtypemap[cls._get_typekey(typename)]

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
            setattr(obj, self._name, FilterSet._from_iterable(value))
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
    """Exclusion and inclusion rules for filtering a namespace.

    Namespace filtering rules can be of two types, :const:`EXCLUDE` and
    :const:`INCLUDE` rules, and of five "flavors":

        - `name`: match a variable name exactly;
        - `regex`: match a variable name by regular expression;
        - `id`: match a variable value by id;
        - `type`: match a variable value by type (using ``isinstance``);
        - `func`: callable filter, match a variable name and/or value by an
          arbitrary logic.

    A `name` filter is specified by a simple string, e.g. ``'some_var'``. If its
    value is not a valid Python identifier, except for the special `type` case
    below, it is treated as a regular expression instead.

    A `regex` filter is specified either by a string containing a regular
    expression, e.g. ``r'\w+_\d+'``, or by a :py:class:`re.Pattern` object.

    An `id` filter is specified by an ``int`` that corresponds to the id of an
    object. For example, to exclude a specific object ``obj`` that may be
    assigned to multiple variables, just use ``id(obj)`` as an `id` filter.

    A `type` filter is specified by a type-object, e.g. ``list`` or
    ``type(some_var)``, or by a string with the format ``"type:<typename>"``,
    where ``<typename>`` is a type name (case insensitive) known by ``dill`` ,
    e.g. ``"type:function"`` or ``"type: FunctionType"``.  These include all
    the types defined in the module :py:mod:`types` and many more.

    Finally, a `func` filter can be any callable that accepts a single argument and
    returns a boolean value, being it `True` if the object should be excluded
    (or included, depending on how the filter is used) or `False` if it should
    *not* be excluded (or included).

    The single argument passed to `func` filters is an instance of
    :py:class:`NamedObject`, an object with two attributes: ``name`` is the
    variable's name in the namespace and ``value`` is the object that it refers
    to.  Below are some examples of `func` filters.

    A strict type filter, exclude ``int`` but not ``bool`` (an ``int`` subclass):

    >>> int_filter = lambda obj: type(obj) == int

    Exclude objects that were renamed after definition:

    >>> renamed_filter = lambda obj: obj.name != getattr(obj.value, '__name__', obj.name)

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

    The order that the exclusion and inclusion filters are added is irrelevant
    because **exclusion filters are always applied first**.  Therefore,
    generally the rules work as a blocklist, with inclusion rules acting as
    exceptions to the exclusion rules.  However, **if there are only inclusion
    filters, the rules work as an allowlist** instead, and only the variables
    matched by the inclusion filters are kept.
    """
    __slots__ = '_exclude', '_include', '__weakref__'
    exclude = _FilterSetDescriptor()
    include = _FilterSetDescriptor()

    def __init__(self, rules: Union[Iterable[Rule], FilterRules] = None):
        self._exclude = FilterSet()
        self._include = FilterSet()
        if rules is not None:
            self.update(rules)

    def __repr__(self) -> str:
        """Compact representation of FilterSet."""
        COLUMNS = 78
        desc = ["<FilterRules:"]
        for attr in ('exclude', 'include'):
            set_desc = getattr(self, attr, None)
            if set_desc is None:
                continue
            set_desc = repr(set_desc)
            set_desc = re.sub(r'(\w+=set\(\)(, )?)', '', set_desc).replace(', )', ')')
            if len(set_desc) > COLUMNS:
                set_desc = ["FilterSet("] + re.findall(r'\w+={.+?}', set_desc)
                set_desc = ",\n    ".join(set_desc) + "\n  )"
            set_desc = "%s=%s" % (attr, set_desc)
            if attr == 'exclude' and hasattr(self, 'include'):
                set_desc += ','
            desc.append(set_desc)
        if len(desc) == 1:
            desc += ["NOT SET"]
        sep = "\n  " if sum(len(x) for x in desc) > COLUMNS else " "
        return sep.join(desc) + ">"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, FilterRules):
            return NotImplemented
        MISSING = object()
        self_exclude = getattr(self, 'exclude', MISSING)
        self_include = getattr(self, 'include', MISSING)
        other_exclude = getattr(other, 'exclude', MISSING)
        other_include = getattr(other, 'include', MISSING)
        return self_exclude == other_exclude and self_include == other_include

    # Proxy add(), discard(), remove() and clear() to FilterSets.
    def __proxy__(self,
        method: str,
        filter: Filter,
        *,
        rule_type: RuleType = RuleType.EXCLUDE,
    ) -> None:
        """Call 'method' over FilterSet specified by 'rule_type'."""
        if not isinstance(rule_type, RuleType):
            raise ValueError("invalid rule type: %r (must be one of %r)" % (rule_type, list(RuleType)))
        filter_set = getattr(self, rule_type.name.lower())
        getattr(filter_set, method)(filter)
    add = partialmethod(__proxy__, 'add')
    discard = partialmethod(__proxy__, 'discard')
    remove = partialmethod(__proxy__, 'remove')
    def clear(self) -> None:
        self.exclude.clear()
        self.include.clear()

    def update(self, rules: Union[Iterable[Rule], FilterRules]) -> None:
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

    def _apply_filters(self,
        filter_set: FilterSet,
        objects: Iterable[NamedObject]
    ) -> Iterator[NamedObject]:
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

    def apply_filters(self, namespace: Dict[str, Any]) -> Dict[str, Any]:
        """Apply filters to dictionary with names as keys."""
        if not namespace or not (self.exclude or self.include):
            return namespace
        # Protect agains dict changes during the call.
        namespace_copy = namespace.copy()
        all_objs = [NamedObject(item) for item in namespace_copy.items()]

        if self.exclude:
            include_names = {obj.name for obj in self._apply_filters(self.exclude, all_objs)}
            exclude_objs = [obj for obj in all_objs if obj.name not in include_names]
        else:
            # Treat this rule set as an allowlist.
            exclude_objs = all_objs
        if self.include and exclude_objs:
            exclude_objs = list(self._apply_filters(self.include, exclude_objs))

        if not exclude_objs:
            return namespace
        if len(exclude_objs) == len(namespace):
            warnings.warn(
                "the exclusion/inclusion rules applied have excluded all %d items" % len(all_objs),
                _dill.PicklingWarning,
                stacklevel=2
            )
            return {}
        for obj in exclude_objs:
            del namespace_copy[obj.name]
        return namespace_copy


## Filter factories ##

import collections
import collections.abc
import random
from statistics import mean
from sys import getsizeof
from types import ModuleType

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
    # Cover "true" collections from 'builtins', 'collections' and 'collections.abc'.
    COLLECTION_TYPES = (
        list,
        tuple,
        collections.deque,
        collections.UserList,
        collections.abc.Mapping,    # dict, OrderedDict, UserDict, etc.
        collections.abc.Set,        # set, frozenset
    )
    MINIMUM_SIZE = getsizeof(None, 16)
    MISSING_SLOT = object()

    def __init__(self,
        limit: Union[int, float, str],
        recursive: bool = True,
    ) -> FilterFunction:
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
    def estimate_size(cls, obj: Any, memo: Optional[set] = None) -> int:
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
