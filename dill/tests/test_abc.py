import abc
import dill

def test_deserialize_abc():
  class MyMeta(metaclass=abc.ABCMeta):
    _not_abc_impl = 1
  MyMeta.__module__ = '__main__'

  class MyImpl:
    pass

  MyMeta.register(MyImpl)
  assert isinstance(MyImpl(),  MyMeta)
  # Tests that dill doesn't crash pickling _abc._abc_data.
  cls = dill.loads(dill.dumps(MyMeta))
  # Dill doesn't serialise the ABC registry, although it's not clear if
  # that's on purpose or not.
  assert not isinstance(MyImpl(), cls)
  cls.register(MyImpl)
  assert isinstance(MyImpl(), cls)


if __name__ == '__main__':
    test_deserialize_abc()
