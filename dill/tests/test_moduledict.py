#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import dill
dill.settings['recurse'] = True

def f(func):
  def w(*args):
    return f(*args)
  return w

@f
def f2(): pass

# check when __main__ and on import
def test_decorated():
  assert dill.pickles(f2)


import doctest
import logging
logging.basicConfig(level=logging.DEBUG)

class SomeUnreferencedUnpicklableClass(object):
    def __reduce__(self):
        raise Exception

unpicklable = SomeUnreferencedUnpicklableClass()

# This works fine outside of Doctest:
def test_normal():
    serialized = dill.dumps(lambda x: x)

# should not try to pickle unpicklable object in __globals__
def tests():
    """
    >>> serialized = dill.dumps(lambda x: x)
    """
    return

#print("\n\nRunning Doctest:")
def test_doctest():
    doctest.testmod()


def test_named_dict():
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        for name in ('', None, False, 42, 'not_a_module', 'logging'):
            value = {'__name__': name, 'value': [1, 2]}
            copied = dill.copy([value, value], protocol=protocol)
            assert copied[0] == value
            assert copied[0] is copied[1]
            assert copied[0] is not value


def test_module_dict_reference():
    for protocol in range(dill.HIGHEST_PROTOCOL + 1):
        assert dill.copy(logging.__dict__, protocol=protocol) is logging.__dict__


if __name__ == '__main__':
    test_decorated()
    test_normal()
    test_doctest()
    test_named_dict()
    test_module_dict_reference()
