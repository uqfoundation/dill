import dill as pickle
try:
    from StringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO

def my_fn(x):
    return x * 17

obj = lambda : my_fn(34)
assert obj() == 578

obj_io = StringIO.StringIO()
pickler = pickle.Pickler(obj_io)
pickler.dump(obj)

obj_str = obj_io.getvalue()

obj2_io = StringIO.StringIO(obj_str)
unpickler = pickle.Unpickler(obj2_io)
obj2 = unpickler.load()

assert obj2() == 578
