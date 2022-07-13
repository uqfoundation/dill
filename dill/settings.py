#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
global settings for Pickler
"""

from __future__ import annotations

__all__ = ['settings', 'ModuleRules']

from pickle import DEFAULT_PROTOCOL
from ._utils import FilterRules, RuleType

settings = {
   #'main' : None,
    'protocol' : DEFAULT_PROTOCOL,
    'byref' : False,
   #'strictio' : False,
    'fmode' : 0, #HANDLE_FMODE
    'recurse' : False,
    'ignore' : False,
}

del DEFAULT_PROTOCOL

class ModuleRules(FilterRules):
    __slots__ = 'module', '_parent', '__dict__'
    _fields = tuple(x.lstrip('_') for x in FilterRules.__slots__)
    def __init__(self,
        module: str,
        parent: ModuleRules = None,
        rules: Union[Iterable[Rule], FilterRules] = None
    ):
        super().__setattr__('module', module)
        super().__setattr__('_parent', parent)
        # Don't call super().__init__().
        if rules is not None:
            super().__init__(rules)
    def __repr__(self):
        desc = "DEFAULT" if self.module == 'DEFAULT' else "for %r" % self.module
        return "<ModuleRules %s %s>" % (desc, super().__repr__())
    def __setattr__(self, name, value):
        if name in FilterRules.__slots__:
            # Don't interfere with superclass attributes.
            super().__setattr__(name, value)
        elif name in self._fields:
            if not any(hasattr(self, x) for x in FilterRules.__slots__):
                # Initialize other. This is not a placeholder anymore.
                other = '_include' if name == 'exclude' else '_exclude'
                super().__setattr__(other, ())
            super().__setattr__(name, value)
        else:
            # Create a child node for submodule 'name'.
            super().__setattr__(name, ModuleRules(parent=self, module=name, rules=value))
    def __setitem__(self, name, value):
        if '.' not in name:
            setattr(self, name, value)
        else:
            module, _, submodules = name.partition('.')
            if module not in self.__dict__:
                # Create a placeholder node, like logging.PlaceHolder.
                setattr(self, module, None)
            mod_rules = getattr(self, module)
            mod_rules[submodules] = value
    def __getitem__(self, name):
        module, _, submodules = name.partition('.')
        mod_rules = getattr(self, module)
        if not submodules:
            return mod_rules
        else:
            return mod_rules[submodules]
    def get(self, name: str, default: ModuleRules = None):
        try:
            return self[name]
        except AttributeError:
            return default
    def get_filters(self, rule_type: RuleType):
        if not isinstance(rule_type, RuleType):
            raise ValueError("invalid rule type: %r (must be one of %r)" % (rule_type, list(RuleType)))
        try:
            return getattr(self, rule_type.name.lower())
        except AttributeError:
            # 'self' is a placeholder, 'exclude' and 'include' are unset.
            if self._parent is None:
                raise
            return self._parent.get_filters(rule_type)

settings['dump_module'] = ModuleRules('DEFAULT', rules=())
