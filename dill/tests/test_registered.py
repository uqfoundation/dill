#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2022-2025 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
test pickling registered objects
"""

import io

import dill
from dill._objects import failures, registered, succeeds

# Pytest replaces stdio streams with capture objects that are not picklable,
# which breaks round-tripping a handful of stdlib helpers that hang on to
# those streams. Point them at simple in-memory buffers so the coverage stays
# representative regardless of the test harness.
if 'PrettyPrinterType' in succeeds:
    succeeds['PrettyPrinterType']._stream = io.StringIO()
if 'StreamHandlerType' in succeeds:
    succeeds['StreamHandlerType'].stream = io.StringIO()
import warnings
warnings.filterwarnings('ignore')

def check(d, ok=True):
    res = []
    for k,v in d.items():
        try:
            z = dill.copy(v)
            if ok: res.append(k)
        except:
            if not ok: res.append(k)
    return res

fails = check(failures)
try:
    assert not bool(fails)
except AssertionError as e:
    print("FAILS: %s" % fails)
    raise e from None

register = check(registered, ok=False)
try:
    assert not bool(register)
except AssertionError as e:
    print("REGISTER: %s" % register)
    raise e from None

success = check(succeeds, ok=False)
try:
    assert not bool(success)
except AssertionError as e:
    print("SUCCESS: %s" % success)
    raise e from None

import builtins
import types
q = dill._dill._reverse_typemap
p = {k:v for k,v in q.items() if k not in vars(builtins) and k not in vars(types)}

diff = set(p.keys()).difference(registered.keys())
try:
    assert not bool(diff)
except AssertionError as e:
    print("DIFF: %s" % diff)
    raise e from None

miss = set(registered.keys()).difference(p.keys())
try:
    assert not bool(miss)
except AssertionError as e:
    print("MISS: %s" % miss)
    raise e from None
