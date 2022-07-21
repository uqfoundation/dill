import dill
from dill._objects import failures, registered, succeeds
import warnings
warnings.filterwarnings('ignore')

def check(d, ok=True):
    res = []
    for k,v in d.items():
        try:
            z = dill.copy(v)
            if ok: res.append(k)
        except:
            if not ok: res.append(k)
    return res

assert not bool(check(failures))
assert not bool(check(registered, ok=False))
assert not bool(check(succeeds, ok=False))

import builtins
import types
q = dill._dill._reverse_typemap
p = {k:v for k,v in q.items() if k not in vars(builtins) and k not in vars(types)}
assert not bool(set(p.keys()).difference(registered.keys()))
assert not bool(set(registered.keys()).difference(p.keys()))

