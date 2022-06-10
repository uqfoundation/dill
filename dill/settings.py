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

__all__ = ['settings', 'Settings']

try:
    from pickle import DEFAULT_PROTOCOL
except ImportError:
    from pickle import HIGHEST_PROTOCOL as DEFAULT_PROTOCOL
from collections.abc import MutableMapping
from ._utils import AttrDict, ExcludeRules

class Settings(AttrDict):
    """allow multiple level attribute access"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, value in tuple(self.items()):
            if isinstance(value, MutableMapping):
                self[key] = Settings(value)
    @staticmethod
    def _cast_dict(obj):
        return Settings(obj) if isinstance(obj, MutableMapping) else obj
    def __setitem__(self, key, value):
        super().__setitem__(key, self._cast_dict(value))
    def setdefault(self, key, default=None):
        super().setdefault(key, self._cast_dict(default))
    def update(self, *args, **kwargs):
        super().update(Settings(*args, **kwargs))
    def __setattr__(self, key, value):
        super().__setattr__(key, _cast_dict(value))
    def copy(self):
        # Deep copy.
        copy = Settings(self)
        for key, value in self.items():
            if isinstance(value, Settings):
                copy[key] = value.copy()
        return copy

settings = Settings({
   #'main' : None,
    'protocol' : DEFAULT_PROTOCOL,
    'byref' : False,
   #'strictio' : False,
    'fmode' : 0, #HANDLE_FMODE
    'recurse' : False,
    'ignore' : False,
    'session_exclude': ExcludeRules(),
})

del DEFAULT_PROTOCOL

