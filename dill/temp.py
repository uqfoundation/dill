#!/usr/bin/env python

"""
Methods for serialized objects (or source code) stored in temporary files
and file-like objects.
"""
#XXX: better instead to have functions write to any given file-like object ?
#XXX: currently, all file-like objects are created by the function...

from __future__ import absolute_import
__all__ = ['dump_source', 'dump', 'dumpIO_source', 'dumpIO']

import sys
PYTHON3 = (hex(sys.hexversion) >= '0x30000f0')
def b(x): # deal with b'foo' versus 'foo'
    import codecs
    return codecs.latin_1_encode(x)[0]

def dump_source(object, **kwds):
    """write object source to a NamedTemporaryFile (instead of dill.dump)
Loads with "import" or "open".  Returns the filehandle.

    >>> f = lambda x: x**2
    >>> pyfile = dill.temp.dump_source(f, alias='_f')
    >>> exec(open(pyfile.name).read())
    >>> _f(4)
    16

    >>> f = lambda x: x**2
    >>> pyfile = dill.temp.dump_source(f, dir='.')
    >>> modulename = os.path.basename(pyfile.name).split('.py')[0]
    >>> exec('from %s import f as _f' % modulename)
    >>> _f(4)
    16

Optional kwds:
    If 'alias' is specified, the object will be renamed to the given string.

    If 'prefix' is specified, the file name will begin with that prefix,
    otherwise a default prefix is used.
    
    If 'dir' is specified, the file will be created in that directory,
    otherwise a default directory is used.
    
    If 'text' is specified and true, the file is opened in text
    mode.  Else (the default) the file is opened in binary mode.  On
    some operating systems, this makes no difference.

NOTE: Keep the return value for as long as you want your file to exist !
    """ #XXX: write a "load_source"?
    from .source import getsource
    import tempfile
    kwds.pop('suffix', '') # this is *always* '.py'
    alias = kwds.pop('alias', '') #XXX: include an alias so a name is known
    #XXX: assumes kwds['dir'] is writable and on $PYTHONPATH
    file = tempfile.NamedTemporaryFile(suffix='.py', **kwds)
    file.write(b(''.join(getsource(object, alias=alias))))
    file.flush()
    return file

def dump(object, **kwds):
    """dill.dump of object to a NamedTemporaryFile.
Loads with "dill.load".  Returns the filehandle.

    >>> dumpfile = dill.temp.dump([1, 2, 3, 4, 5])
    >>> dill.load(open(dumpfile.name, 'rb'))
    [1, 2, 3, 4, 5]

Optional kwds:
    If 'suffix' is specified, the file name will end with that suffix,
    otherwise there will be no suffix.
    
    If 'prefix' is specified, the file name will begin with that prefix,
    otherwise a default prefix is used.
    
    If 'dir' is specified, the file will be created in that directory,
    otherwise a default directory is used.
    
    If 'text' is specified and true, the file is opened in text
    mode.  Else (the default) the file is opened in binary mode.  On
    some operating systems, this makes no difference.

NOTE: Keep the return value for as long as you want your file to exist !
    """
    import dill as pickle
    import tempfile
    file = tempfile.NamedTemporaryFile(**kwds)
    pickle.dump(object, file)
    file.flush()
    return file

def dumpIO(object, **kwds):
    """dill.dump of object to a buffer.
Loads with "dill.load".  Returns the buffer object.

    >>> dumpfile = dill.temp.dumpIO([1, 2, 3, 4, 5])
    >>> dill.load(StringIO(dumpfile.getvalue()))
    [1, 2, 3, 4, 5]
    """
    import dill as pickle
    if PYTHON3:
        from io import BytesIO as StringIO
    else:
        from StringIO import StringIO
    file = StringIO()
    pickle.dump(object, file)
    file.flush()
    return file

def dumpIO_source(object, **kwds):
    """write object source to a buffer (instead of dill.dump)
Loads by reading buffer.  Returns the buffer object.

    >>> f = lambda x:x**2
    >>> pyfile = dill.temp.dumpIO_source(f, alias='_f')
    >>> exec(pyfile.getvalue())
    >>> _f(4)
    16

Optional kwds:
    If 'alias' is specified, the object will be renamed to the given string.
    """
    from .source import getsource
    if PYTHON3:
        from io import BytesIO as StringIO
    else:
        from StringIO import StringIO
    alias = kwds.pop('alias', '') #XXX: include an alias so a name is known
    #XXX: assumes kwds['dir'] is writable and on $PYTHONPATH
    file = StringIO()
    file.write(b(''.join(getsource(object, alias=alias))))
    file.flush()
    return file


del absolute_import, sys


# EOF
