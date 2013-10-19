from dill.temp import dump, dump_source, dumpIO, dumpIO_source
from dill import load

import sys
PYTHON3 = (hex(sys.hexversion) >= '0x30000f0')

if PYTHON3:
    from io import BytesIO as StringIO
else:
    from StringIO import StringIO


f = lambda x: x**2
x = [1,2,3,4,5]

pyfile = dump_source(f, alias='_f')
exec(open(pyfile.name).read())
assert _f(4) == f(4)

f = lambda x: x**2 #XXX: needs a refresh...?

pyfile = dumpIO_source(f, alias='_f')
exec(pyfile.getvalue())
assert _f(4) == f(4)

dumpfile = dump(x)
_x = load(open(dumpfile.name, 'rb'))
assert _x == x

dumpfile = dumpIO(x)
_x = load(StringIO(dumpfile.getvalue()))
assert _x == x

