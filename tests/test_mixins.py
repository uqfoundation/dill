#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill

def wtf(x,y,z):
  def zzz():
    return x
  def yyy():
    return y
  def xxx():
    return z
  return zzz,yyy

def quad(a=1, b=1, c=0):
  inverted = [False]
  def invert():
    inverted[0] = not inverted[0]
  def dec(f):
    def func(*args, **kwds):
      x = f(*args, **kwds)
      if inverted[0]: x = -x
      return a*x**2 + b*x + c
    func.__wrapped__ = f
    func.invert = invert
    return func
  return dec


@quad(a=0,b=2)
def double_add(*args):
  return sum(args)

fx = sum([1,2,3])

### to make it interesting...
def quad_factory(a=1,b=1,c=0):
  def dec(f):
    def func(*args,**kwds):
      fx = f(*args,**kwds)
      return a*fx**2 + b*fx + c
    return func
  return dec

@quad_factory(a=0,b=4,c=0)
def quadish(x):
  return x+1

quadratic = quad_factory()

def doubler(f):
  def inner(*args, **kwds):
    fx = f(*args, **kwds)
    return 2*fx
  return inner

@doubler
def quadruple(x):
  return 2*x


if __name__ == '__main__':

  # test mixins
  assert double_add(1,2,3) == 2*fx
  double_add.invert()
  assert double_add(1,2,3) == -2*fx

  _d = dill.copy(double_add)
  assert _d(1,2,3) == -2*fx
  _d.invert()
  assert _d(1,2,3) == 2*fx

  assert _d.__wrapped__(1,2,3) == fx

  # test some stuff from source and pointers
  ds = dill.source
  dd = dill.detect
  assert ds.getsource(dd.freevars(quadish)['f']) == '@quad_factory(a=0,b=4,c=0)\ndef quadish(x):\n  return x+1\n'
  assert ds.getsource(dd.freevars(quadruple)['f']) == '@doubler\ndef quadruple(x):\n  return 2*x\n'
  #XXX: quadratic ?


# EOF
