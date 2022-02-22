#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2013-2016 California Institute of Technology.
# Copyright (c) 2016-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/klepto/blob/master/LICENSE

import sys
from functools import partial
from klepto.keymaps import hashmap
from klepto import NULL
from klepto import signature, keygen
from klepto import _keygen, isvalid
from klepto.tools import IS_PYPY

def bar(x,y,z,a=1,b=2,*args):
  return x+y+z+a+b

def test_signature():
    s = signature(bar)
    assert s == (('x', 'y', 'z', 'a', 'b'), {'a': 1, 'b': 2}, 'args', '')

    # a partial with a 'fixed' x, thus x is 'unsettable' as a keyword
    p = partial(bar, 0)
    s = signature(p)
    assert s == (('y', 'z', 'a', 'b'), {'a': 1, '!x': 0, 'b': 2}, 'args', '')
    '''
    >>> p(0,1)  
        4
    >>> p(0,1,2,3,4,5)
        6
    '''
    # a partial where y is 'unsettable' as a positional argument
    p = partial(bar, y=10)
    s = signature(p)
    assert s == (('x', '!y', 'z', 'a', 'b'), {'a': 1, 'y': 10, 'b': 2}, 'args', '')
    '''
    >>> p(0,1,2)
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
        TypeError: bar() got multiple values for keyword argument 'y'
    >>> p(0,z=2)
        15
    >>> p(0,y=1,z=2)
        6
    '''


#################################################################
# test _keygen 
def test_keygen():
    # a partial with a 'fixed' x, and positionally 'unsettable' b
    p = partial(bar, 0,b=10)
    s = signature(p)
    assert s == (('y', 'z', 'a', '!b'), {'a': 1, '!x': 0, 'b': 10}, 'args', '')

    ignored = (0,1,3,5,'*','b','c')
    user_args = ('0','1','2','3','4','5','6')
    user_kwds = {'a':'10','b':'20','c':'30','d':'40'}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ()
    assert key_kwds == {'a': '2', 'c': NULL, 'b': NULL, 'd': '40', 'y': NULL, 'z': NULL}

    ignored = (0,1,3,5,'**','b','c')
    user_args = ('0','1','2','3','4','5','6')
    user_kwds = {'a':'10','b':'20','c':'30','d':'40'}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ('4', NULL, '6')
    assert key_kwds == {'a': '2', 'b': NULL, 'y': NULL, 'z': NULL}

    ignored = ('*','**')
    user_args = ('0','1','2','3','4','5','6')
    user_kwds = {'a':'10','b':'20','c':'30','d':'40'}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ()
    assert key_kwds == {'a': '2', 'b': '3', 'y': '0', 'z': '1'}

    ignored = (0,2)
    user_args = ('0','1','2','3','4','5','6')
    user_kwds = {'a':'10','b':'20','c':'30','d':'40'}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ('4', '5', '6')
    assert key_kwds == {'a': NULL, 'c': '30', 'b': '3', 'd':'40', 'y': NULL, 'z': '1'}

    ignored = (0,)
    user_args = ('0','1','2','3','4','5','6')
    user_kwds = {'a':'10','b':'20','c':'30','d':'40','y':50}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ('4', '5', '6')
    assert key_kwds == {'a': '2', 'c': '30', 'b': '3', 'd':'40', 'y': NULL, 'z': '1'}

    ignored = ('a','y','c')
    user_args = ('0','1','2','3','4','5','6')
    user_kwds = {'a':'10','b':'20','c':'30','d':'40','y':50}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ('4', '5', '6')
    assert key_kwds == {'a': NULL, 'c': NULL, 'b': '3', 'd':'40', 'y': NULL, 'z': '1'}

    ignored = (1,5,'a','y','c')
    user_args = ('0','1')
    user_kwds = {}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ()
    assert key_kwds == {'a': NULL, 'y': NULL, 'b': 10, 'z': NULL} #XXX: c?

    ignored = (1,5,'a','y','c')
    user_args = ()
    user_kwds = {'c':'30','d':'40','y':50}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ()
    assert key_kwds == {'a': NULL, 'y': NULL, 'c': NULL, 'd': '40', 'b': 10, 'z': NULL}

    ignored = (1,5,'a','c')
    user_args = ('0','1')
    user_kwds = {}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ()
    assert key_kwds == {'a': NULL, 'y': '0', 'b': 10, 'z': NULL} #XXX: c?

    ignored = ()
    user_args = ('0',)
    user_kwds = {'c':'30'}
    key_args,key_kwds = _keygen(p, ignored, *user_args, **user_kwds) 
    assert key_args == ()
    assert key_kwds == {'a': 1, 'y': '0', 'b': 10, 'c': '30'}


#################################################################
@keygen('x','**')
def foo(x,y,z=2):
    return x+y+z

def test_keygen_foo():
    assert foo(0,1,2) == ('x', NULL, 'y', 1, 'z', 2)
    assert foo.valid() == True
    assert foo(10,1,2) == ('x', NULL, 'y', 1, 'z', 2)
    assert foo(0,1) == ('x', NULL, 'y', 1, 'z', 2)
    assert foo(0,1,3) ==  ('x', NULL, 'y', 1, 'z', 3)
    assert foo(0,1,r=3) == ('x', NULL, 'y', 1, 'z', 2)
    assert foo.valid() == False
    assert foo(0,1,x=1) == ('x', NULL, 'y', 1, 'z', 2)
    assert foo.valid() == False
    res2 = ('x', NULL, 'y', 2, 'z', 10)
    assert foo(10,y=2,z=10) == res2
    assert foo.valid() == True
    res1 = ('x', NULL, 'y', 1, 'z', 10)
    assert foo(0,1,z=10) == res1
    assert foo.valid() == True
    assert foo.call() == 11
    h = hashmap(algorithm='md5')
    foo.register(h)
    if hex(sys.hexversion) < '0x30300f0':
        _hash1 = '2c8d801f4078eba873a5fb6909ab0f8d'
        _hash2 = '949883b97d9fda9c8fe6bd468fe90af9'
    else: # python 3.3 has hash randomization, apparently
        from klepto.crypto import hash
        _hash1 = hash(res1, 'md5')
        _hash2 = hash(res2, 'md5')
    assert foo(0,1,z=10) == _hash1
    assert str(foo.keymap()) == str(h)
    assert foo.key() == _hash1
    assert foo(10,y=1,z=10) == _hash1
    assert foo(10,y=2,z=10) == _hash2

#################################################################
# test special cases (builtins) for signature, isvalid, _keygen
def add(x,y):
    return x+y

def test_special():
    p = partial(add, 0,x=0)
    p2 = partial(add, z=0)
    p3 = partial(add, 0)

    
    if IS_PYPY: # builtins in PYPY are python functions
        if hex(sys.hexversion) < '0x3080cf0':
            base, exp, mod = 'base', 'exponent', 'modulus'
        else:
            base, exp, mod = 'base', 'exp', 'mod'
        assert signature(pow, safe=True) == ((base, exp, mod), {mod: None}, '', '')
    else:
        assert signature(pow, safe=True) == (None, None, None, None)
    assert signature(p, safe=True) == (None, None, None, None)
    assert signature(p2, safe=True) == (('x', 'y'), {'z': 0}, '', '')
    assert signature(p3, safe=True) == (('y',), {'!x': 0}, '', '')
    if IS_PYPY: # PYPY bug in ArgSpec for min, so use pow
        assert isvalid(pow, 0,1) == True
        assert isvalid(pow, 0) == False
        assert isvalid(pow) == False
    else: # python >= 3.5 bug in ArgSpec for pow, so use min
        assert isvalid(min, 0,1) == True
        assert isvalid(min, 0) == False
        assert isvalid(min) == False
    assert isvalid(p, 0,1) == False
    assert isvalid(p, 0) == False
    assert isvalid(p) == False
    assert isvalid(p2, 0,1) == False
    assert isvalid(p2, 0) == False
    assert isvalid(p2) == False
    assert isvalid(p3, 0,1) == False
    assert isvalid(p3, 0) == True
    assert isvalid(p3) == False
    assert _keygen(p3, [], 0) == ((), {'y': 0})
    assert _keygen(p2, [], 0) == ((), {'x': 0, 'z': 0})
    assert _keygen(p, [], 0) == ((0,), {})
    assert _keygen(min, [], x=0,y=1) == ((), {'y': 1, 'x': 0})
    assert _keygen(min, [], 0,1) == ((0,1), {})
    assert _keygen(min, [], 0) == ((0,), {})
    assert _keygen(min, 'x', 0) == ((0,), {})
    assert _keygen(min, ['x','y'], 0) == ((0,), {})
    assert _keygen(min, [0,1], 0) == ((NULL,), {}) if IS_PYPY else ((0,), {})
    assert _keygen(min, ['*'], 0) == ((), {}) if IS_PYPY else ((0,), {})


if __name__ == '__main__':
    test_signature()
    test_keygen()
    test_keygen_foo()
    test_special()
