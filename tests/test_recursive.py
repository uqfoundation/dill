import dill
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


if __name__ == '__main__':
    test_super()
