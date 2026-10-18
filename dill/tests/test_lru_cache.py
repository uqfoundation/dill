#!/usr/bin/env python
#
# License: 3-clause BSD. The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import functools
import dill


def test_wrapper_state():
    for maxsize in (0, 2, 128, None):
        for typed in (False, True):
            cached = functools.lru_cache(maxsize=maxsize, typed=typed)(lambda x: x * 2)
            cached.terminal = True
            cached.direction = -1
            cached.metadata = {'labels': ['simulation']}
            cached.alias = cached.metadata
            cached.self = cached
            cached.__name__ = 'custom_name'
            copied = dill.copy(cached)
            assert copied.cache_parameters() == cached.cache_parameters()
            assert copied(3) == cached(3)
            assert copied.terminal is True
            assert copied.direction == -1
            assert copied.metadata == cached.metadata
            assert copied.metadata is not cached.metadata
            assert copied.alias is copied.metadata
            assert copied.self is copied
            assert copied.__name__ == 'custom_name'


if __name__ == '__main__':
    test_wrapper_state()
