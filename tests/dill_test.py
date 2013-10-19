#!/usr/bin/env python
"""
test dill's ability to handle nested functions
"""

import dill as pickle
#import pickle

# the nested function: pickle should fail here, but dill is ok.
def adder(augend):
  zero = [0]
  def inner(addend):
    return addend+augend+zero[0]
  return inner

# rewrite the nested function using a class: standard pickle should work here.
class cadder(object):
  def __init__(self,augend):
    self.augend = augend
    self.zero = [0]
  def __call__(self,addend):
    return addend+self.augend+self.zero[0]

# rewrite again, but as an old-style class
class c2adder:
  def __init__(self,augend):
    self.augend = augend
    self.zero = [0]
  def __call__(self,addend):
    return addend+self.augend+self.zero[0]

# some basic stuff
a = [0,1,2]
import math

# some basic class stuff
class basic(object):
  pass
class basic2:
  pass


if __name__ == '__main__':
  x = 5; y = 1

  # pickled basic stuff
  pa = pickle.dumps(a)
  pmath = pickle.dumps(math) #XXX: FAILS in pickle
  pmap = pickle.dumps(map)
  # ...
  la = pickle.loads(pa)
  lmath = pickle.loads(pmath)
  lmap = pickle.loads(pmap)
  assert list(map(math.sin,a)) == list(lmap(lmath.sin,la))

  # pickled basic class stuff
  pbasic2 = pickle.dumps(basic2)
  _pbasic2 = pickle.loads(pbasic2)()
  pbasic = pickle.dumps(basic)
  _pbasic = pickle.loads(pbasic)()

  # pickled c2adder
  pc2adder = pickle.dumps(c2adder)
  pc2add5 = pickle.loads(pc2adder)(x)
  assert pc2add5(y) == x+y

  # pickled cadder
  pcadder = pickle.dumps(cadder)
  pcadd5 = pickle.loads(pcadder)(x)
  assert pcadd5(y) == x+y

  # raw adder and inner
  add5 = adder(x)
  assert add5(y) == x+y

  # pickled adder
  padder = pickle.dumps(adder)
  padd5 = pickle.loads(padder)(x)
  assert padd5(y) == x+y

  # pickled inner
  pinner = pickle.dumps(add5) #XXX: FAILS in pickle
  p5add = pickle.loads(pinner)
  assert p5add(y) == x+y

