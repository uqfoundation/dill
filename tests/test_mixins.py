import dill

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

assert double_add(1,2,3) == 2*fx
double_add.invert()
assert double_add(1,2,3) == -2*fx

_d = dill.copy(double_add)
assert _d(1,2,3) == -2*fx
_d.invert()
assert _d(1,2,3) == 2*fx

assert _d.__wrapped__(1,2,3) == fx


# EOF
