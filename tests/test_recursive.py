import dill
from functools import partial
import sys
from dill.dill import PY3, OLDER
_super = super

class obj1(object):
    def __init__(self):
        super(obj1, self).__init__()

class obj2(object):
    def __init__(self):
        _super(obj2, self).__init__()

class obj3(object):
    super_ = super
    def __init__(self):
        obj3.super_(obj3, self).__init__()


def test_super():
    assert dill.copy(obj1(), byref=True)
    assert dill.copy(obj1(), byref=True, recurse=True)
    assert dill.copy(obj1(), recurse=True)
    assert dill.copy(obj1())

    assert dill.copy(obj2(), byref=True)
    assert dill.copy(obj2(), byref=True, recurse=True)
    assert dill.copy(obj2(), recurse=True)
    assert dill.copy(obj2())

    assert dill.copy(obj3(), byref=True)
    assert dill.copy(obj3(), byref=True, recurse=True)
    assert dill.copy(obj3(), recurse=True)
    assert dill.copy(obj3())


def get_trigger(model):
    pass

class Machine(object):
    def __init__(self):
        self.child = Model()
        self.trigger = partial(get_trigger, self)
        self.child.trigger = partial(get_trigger, self.child)

class Model(object):
    pass



def test_partial():
    assert dill.copy(Machine(), byref=True)
    assert dill.copy(Machine(), byref=True, recurse=True)
    assert dill.copy(Machine(), recurse=True)
    assert dill.copy(Machine())



if __name__ == '__main__':
    test_super()
    if not OLDER: 
        test_partial()
