#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Author: Anirudh Vegesana (avegesan@cs.stanford.edu)
# Copyright (c) 2021-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import dill
from dill._dill import OLD310, MAPPING_PROXY_TRICK, DictProxyType
import subprocess
import sys
from collections import OrderedDict

def test_dictproxy():
    assert dill.copy(DictProxyType({'a': 2}))

def test_dictviews():
    x = {'a': 1}
    assert dill.copy(x.keys())
    assert dill.copy(x.values())
    assert dill.copy(x.items())

def test_dictproxy_trick():
    if not OLD310 and MAPPING_PROXY_TRICK:
        x = {'a': 1}
        all_views = (x.values(), x.items(), x.keys(), x)
        seperate_views = dill.copy(all_views)
        new_x = seperate_views[-1]
        new_x['b'] = 2
        new_x['c'] = 1
        assert len(new_x) == 3 and len(x) == 1
        assert len(seperate_views[0]) == 3 and len(all_views[0]) == 1
        assert len(seperate_views[1]) == 3 and len(all_views[1]) == 1
        assert len(seperate_views[2]) == 3 and len(all_views[2]) == 1
        assert dict(all_views[1]) == x
        assert dict(seperate_views[1]) == new_x

def test_pure_python_ordereddict_views():
    # Select the stdlib fallback in a subprocess without changing this process.
    ordered = OrderedDict([('b', 2), ('a', 1)])
    artifacts = [dill.dumps(tuple(getattr(ordered, name)() for name in
                                 ('keys', 'values', 'items')), protocol=protocol)
                 for protocol in (4, 5)]
    subprocess.run([sys.executable, '-c', '''
import _collections
import collections
import importlib
import runpy
import sys

native = getattr(_collections, 'OrderedDict', None)
if native is not None:
    del _collections.OrderedDict
importlib.reload(collections)
if native is not None:
    _collections.OrderedDict = native
assert isinstance(collections.OrderedDict.keys, type(lambda: None))
import dill

ordered = collections.OrderedDict([('b', 2), ('a', 1)])
for name in ('keys', 'values', 'items'):
    view = getattr(ordered, name)()
    for protocol in (4, 5):
        restored = dill.loads(dill.dumps(view, protocol=protocol))
        assert type(restored) is type(view)
        assert list(restored) == list(view)
for data in dill.loads(sys.stdin.buffer.read()):
    restored = dill.loads(data)
    assert [list(view) for view in restored] == [['b', 'a'], [2, 1], [('b', 2), ('a', 1)]]
runpy.run_module('dill.tests.test_registered', run_name='__main__')
'''], input=dill.dumps(artifacts), check=True)

if __name__ == '__main__':
    test_dictproxy()
    test_dictviews()
    test_dictproxy_trick()
    test_pure_python_ordereddict_views()
