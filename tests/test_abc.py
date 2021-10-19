#!/usr/bin/env python
"""
test dill's ability to pickle abstract base class objects
"""
import dill as pickle
import abc

from types import FunctionType

pickle.settings['recurse'] = True

class OneTwoThree(abc.ABC):
    @abc.abstractmethod
    def foo(self):
        """A method"""
        pass

    @property
    @abc.abstractmethod
    def bar(self):
        """Property getter"""
        pass

    @bar.setter
    @abc.abstractmethod
    def bar(self, value):
        """Property setter"""
        pass

    @classmethod
    @abc.abstractmethod
    def cfoo(cls):
        """Class method"""
        pass

    @staticmethod
    @abc.abstractmethod
    def sfoo():
        """Static method"""
        pass

class EasyAsAbc(OneTwoThree):
    def __init__(self):
        self._bar = None

    def foo(self):
        return "Instance Method FOO"

    @property
    def bar(self):
        return self._bar

    @bar.setter
    def bar(self, value):
        self._bar = value

    @classmethod
    def cfoo(cls):
        return "Class Method CFOO"

    @staticmethod
    def sfoo():
        return "Static Method SFOO"

def test_abc_non_local():
    assert pickle.loads(pickle.dumps(OneTwoThree)) == OneTwoThree
    assert pickle.loads(pickle.dumps(EasyAsAbc)) == EasyAsAbc
    instance = EasyAsAbc()
    # Set a property that StockPickle can't preserve
    instance.bar = lambda x: x**2
    depickled = pickle.loads(pickle.dumps(instance))
    assert type(depickled) == type(instance)
    assert type(depickled.bar) == FunctionType
    assert depickled.bar(3) == 9
    assert depickled.sfoo() == "Static Method SFOO"
    assert depickled.cfoo() == "Class Method CFOO"
    assert depickled.foo() == "Instance Method FOO"
    print("Tada")

def test_abc_local():
    """
    Test using locally scoped ABC class
    """
    class LocalABC(abc.ABC):
        @abc.abstractmethod
        def foo(self):
            pass

    res = pickle.dumps(LocalABC)
    pik = pickle.loads(res)
    assert type(pik) == type(LocalABC)
    # TODO should work like it does for non local classes
    # <class '__main__.LocalABC'>
    # <class '__main__.test_abc_local.<locals>.LocalABC'>

    class Real(pik):
        def foo(self):
            return "True!"

    real = Real()
    assert real.foo() == "True!"

    try:
        pik()
    except TypeError as e:
        print("Tada: ", e)
    else:
        print('Failed to raise type error')
        assert False

def test_meta_local_no_cache():
    """
    Test calling metaclass and cache registration
    """
    LocalMetaABC = abc.ABCMeta('LocalMetaABC', (), {})

    class ClassyClass:
        pass

    class KlassyClass:
      pass

    LocalMetaABC.register(ClassyClass)

    assert not issubclass(KlassyClass, LocalMetaABC)
    assert issubclass(ClassyClass, LocalMetaABC)

    res = pickle.dumps(LocalMetaABC)
    assert b"ClassyClass" in res
    assert b"KlassyClass" not in res

    pik = pickle.loads(res)
    assert type(pik) == type(LocalMetaABC)

    pik.register(ClassyClass)  # TODO: test should pass without calling register again
    assert not issubclass(KlassyClass, pik)
    assert issubclass(ClassyClass, pik)
    print("tada")

if __name__ == '__main__':
    test_abc_non_local()
    test_abc_local()
    test_meta_local_no_cache()
