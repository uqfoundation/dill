from dill.source import getsource, _get_name, _wrap

f = lambda x: x**2
def g(x): return f(x) - x

def h(x):
  def g(x): return x
  return g(x) - x 

assert getsource(f) == 'f = lambda x: x**2\n'
assert getsource(g) == 'def g(x): return f(x) - x\n'
assert getsource(h) == 'def h(x):\n  def g(x): return x\n  return g(x) - x \n'
assert _get_name(f) == 'f'
assert _get_name(g) == 'g'
assert _get_name(h) == 'h'

assert _wrap(f)(4) == 16
assert _wrap(g)(4) == 12
assert _wrap(h)(4) == 0
