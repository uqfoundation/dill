#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
testing some selected object types
"""

import dill
dill.settings['recurse'] = True

verbose = False

def test_dict_contents():
  c = type.__dict__
  for i,j in c.items():
   #try:
    ok = dill.pickles(j)
   #except Exception:
   #  print ("FAIL: %s with %s" % (i, dill.detect.errors(j)))
    if verbose: print ("%s: %s, %s" % (ok, type(j), j))
    assert ok
  if verbose: print ("")

def _g(x): yield x;

def _f():
  try: raise
  except Exception:
    from sys import exc_info
    e, er, tb = exc_info()
    return er, tb

class _d(object):
  def _method(self):
    pass

from dill import objects
from dill import load_types
load_types(pickleable=True,unpickleable=False)
_newclass = objects['ClassObjectType']
# some clean-up #FIXME: should happen internal to dill
objects['TemporaryFileType'].close()
objects['FileType'].close()
del objects

# getset_descriptor for new-style classes (fails on '_method', if not __main__)
def test_class_descriptors():
  d = _d.__dict__
  for i in d.values():
    ok = dill.pickles(i)
    if verbose: print ("%s: %s, %s" % (ok, type(i), i))
    assert ok
  if verbose: print ("")
  od = _newclass.__dict__
  for i in od.values():
    ok = dill.pickles(i)
    if verbose: print ("%s: %s, %s" % (ok, type(i), i))
    assert ok
  if verbose: print ("")

# (__main__) class instance for new-style classes
def test_class():
  o = _d()
  oo = _newclass()
  ok = dill.pickles(o)
  if verbose: print ("%s: %s, %s" % (ok, type(o), o))
  assert ok
  ok = dill.pickles(oo)
  if verbose: print ("%s: %s, %s" % (ok, type(oo), oo))
  assert ok
  if verbose: print ("")

# frames, generators, and tracebacks (all depend on frame)
def test_frame_related():
  g = _g(1)
  f = g.gi_frame
  e,t = _f()
  _is = lambda ok: ok
  ok = dill.pickles(f)
  if verbose: print ("%s: %s, %s" % (ok, type(f), f))
  assert not ok
  ok = dill.pickles(g)
  if verbose: print ("%s: %s, %s" % (ok, type(g), g))
  assert _is(not ok) #XXX: dill fails
  ok = dill.pickles(t)
  if verbose: print ("%s: %s, %s" % (ok, type(t), t))
  assert not ok #XXX: dill fails
  ok = dill.pickles(e)
  if verbose: print ("%s: %s, %s" % (ok, type(e), e))
  assert ok
  if verbose: print ("")

def test_typing():
  import typing
  x = typing.Any
  assert x == dill.copy(x)
  x = typing.Dict[int, str]
  assert x == dill.copy(x)
  x = typing.List[int]
  assert x == dill.copy(x)
  x = typing.Tuple[int, str]
  assert x == dill.copy(x)
  x = typing.Tuple[int]
  assert x == dill.copy(x)
  x = typing.Tuple[()]
  assert x == dill.copy(x)
  x = typing.Tuple[()].copy_with(())
  assert x == dill.copy(x)
  x = dill.copy(typing.TypeVar("T", bound=int))
  assert isinstance(x, typing.TypeVar)
  assert x.__name__ == "T"
  assert x.__bound__ == int
  x = dill.copy(typing.TypeVar("T", int, str, covariant=True))
  assert x.__constraints__ == (int, str)
  assert x.__covariant__ and not x.__contravariant__
  # a TypeVar that can be found in its module is pickled by reference
  assert dill.copy(typing.AnyStr) is typing.AnyStr
  x = typing.List[typing.AnyStr]
  assert x == dill.copy(x)
  if hasattr(typing, 'NoDefault'): # python >= 3.13
    x = dill.copy(typing.TypeVar("T", default=int))
    assert x.has_default() and x.__default__ is int
  x = dill.copy(typing.ParamSpec("P", bound=int))
  assert isinstance(x, typing.ParamSpec)
  assert x.__name__ == "P"
  assert x.__bound__ == int
  if hasattr(typing, 'TypeVarTuple'): # python >= 3.11
    x = dill.copy(typing.TypeVarTuple("Ts"))
    assert isinstance(x, typing.TypeVarTuple)
    assert x.__name__ == "Ts"
  return

def test_typevar_module():
  import typing
  types = [typing.TypeVar, typing.ParamSpec]
  if hasattr(typing, 'TypeVarTuple'): # python >= 3.11
    types.append(typing.TypeVarTuple)
  for typevar in types:
    value = typevar('Local')
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
      assert dill.copy(value, protocol=protocol).__module__ == value.__module__
    value.__module__ = 'unimportable_typevar_module'
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
      assert dill.copy(value, protocol=protocol).__module__ == value.__module__

def test_type_params():
  # PEP 695 type parameters are not found in the module they claim (typing)
  import sys
  if sys.hexversion < 0x30c00b1: # python < 3.12
    return
  ns = {}
  exec("class Foo[T: int, *Ts, **P]: pass", ns)
  T, Ts, P = ns['Foo'].__type_params__
  for x in (T, Ts, P):
    y = dill.copy(x)
    assert type(y) is type(x)
    assert y.__name__ == x.__name__
    assert y.__module__ == x.__module__
  assert dill.copy(T).__bound__ is int
  Foo = dill.copy(ns['Foo'])
  assert [type(x) for x in Foo.__type_params__] == [type(T), type(Ts), type(P)]


def test_type_alias():
  # PEP 695 type aliases that are not module attributes
  import sys
  if sys.hexversion < 0x30c00b1: # python < 3.12
    return
  import typing
  # a dynamically created alias is not a module attribute
  x = dill.copy(typing.TypeAliasType('MyAlias', list[int]))
  assert type(x) is typing.TypeAliasType
  assert x.__name__ == 'MyAlias'
  assert x.__value__ == list[int]
  # an alias scoped to a class body is not a module attribute either
  ns = {}
  exec("class C:\n  type ClassAlias = set[str]", ns)
  C = dill.copy(ns['C'])
  assert type(C.ClassAlias) is typing.TypeAliasType
  assert C.ClassAlias.__name__ == 'ClassAlias'
  assert C.ClassAlias.__value__ == set[str]
  # an alias that is a module attribute is pickled by reference
  ns2 = {'__name__': '__main__'}
  exec("type Alias = dict[str, int]", ns2)
  sys.modules['__main__'].Alias = ns2['Alias']
  try:
    assert dill.copy(ns2['Alias']) is ns2['Alias']
  finally:
    del sys.modules['__main__'].Alias


def test_typeddict():
  # TypedDict classes are restored through their metaclass, which takes
  # 'total' as a keyword argument; the total=False and required/optional
  # key sets must survive the roundtrip
  import sys
  if sys.hexversion < 0x30900f0: # python < 3.9.3
    return
  if sys.version_info >= (3, 14): # python >= 3.14
    # 3.14 rewrote TypedDict annotation handling (PEP 649 style); the
    # class-body __annotate__ function does not survive dill's by-value
    # class restoration ('NoneType' object is not iterable in
    # typing.__annotate__). This fails identically on upstream dill master
    # (no TypedDict fix), so it is out of scope here.
    return
  import typing
  # class form, saved with total=False: every key must come back optional
  ns = {}
  exec("import typing\nclass TD(typing.TypedDict, total=False):\n"
       "  a: int\n"
       "  b: str", ns)
  TD = dill.copy(ns['TD'])
  assert TD.__total__ is False
  assert TD.__required_keys__ == frozenset()
  assert TD.__optional_keys__ == frozenset({'a', 'b'})
  # functional form, also created with total=False
  FD = typing.TypedDict('FD', {'a': int, 'b': str}, total=False)
  FD = dill.copy(FD)
  assert FD.__required_keys__ == frozenset()
  assert FD.__optional_keys__ == frozenset({'a', 'b'})
  # per-key modifiers exist only on python >= 3.11
  if hasattr(typing, 'Required'): # python >= 3.11
    ns2 = {}
    exec("import typing\nclass TD2(typing.TypedDict, total=False):\n"
         "  a: int\n"
         "  b: typing.Required[str]", ns2)
    TD2 = dill.copy(ns2['TD2'])
    assert TD2.__required_keys__ == frozenset({'b'})
    assert TD2.__optional_keys__ == frozenset({'a'})
    # per-key NotRequired on a total=True TypedDict is unaffected
    ns3 = {}
    exec("import typing\nclass TT(typing.TypedDict):\n"
         "  x: typing.NotRequired[int]", ns3)
    TT = dill.copy(ns3['TT'])
    assert TT.__required_keys__ == frozenset()
    assert TT.__optional_keys__ == frozenset({'x'})
  return


if __name__ == '__main__':
  test_frame_related()
  test_dict_contents()
  test_class()
  test_class_descriptors()
  test_typing()
  test_typevar_module()
  test_type_params()
  test_type_alias()
  test_typeddict()
