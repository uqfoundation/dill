#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE
"""
Extensions to python's 'inspect' module, which can be used
to retrieve information from live python objects. The primary
target of 'dill.source' is to facilitate access to the source
code of interactively defined functions and classes.
"""

__all__ = ['getblocks', 'getsource', '_wrap', 'getname',\
           'getimportable', 'likely_import', '_namespace']

import sys
PYTHON3 = (hex(sys.hexversion) >= '0x30000f0')

def getblocks(object, lstrip=False):# gettype=False):
    """extract code blocks from a code object using stored history"""
    import readline, inspect #, types
    lbuf = readline.get_current_history_length()
    code = [readline.get_history_item(i)+'\n' for i in range(1,lbuf)]
    lnum = 0
    codeblocks = []
   #objtypes = []
    try:
        if PYTHON3:
            fname = object.__name__
            ocode = object.__code__
        else:
            fname = object.func_name
            ocode = object.func_code
        cname = ''
    except AttributeError:
        fname = ''
        ocode = lambda :'__this_is_a_big_dummy_object__'
        ocode.co_code = '__this_is_a_big_dummy_co_code__'
       #try: inspect.getmro(object) #XXX: ensure that it's a class
        if hasattr(object, '__name__'): cname = object.__name__ # class
        else: cname = object.__class__.__name__ # instance
    while lnum < len(code):#-1:
        if fname and code[lnum].lstrip().startswith('def '):
            # functions and methods
            block = inspect.getblock(code[lnum:])
            lnum += len(block)
            if block[0].lstrip().startswith('def %s(' % fname):
                if lstrip: block[0] = block[0].lstrip()
                codeblocks.append(block)
   #            obtypes.append(types.FunctionType)
        elif cname and code[lnum].lstrip().startswith('class '):
            # classes and instances
            block = inspect.getblock(code[lnum:])
            lnum += len(block)
            _cname = ('class %s(' % cname, 'class %s:' % cname)
            if block[0].lstrip().startswith(_cname):
                if lstrip: block[0] = block[0].lstrip()
                codeblocks.append(block)
        elif fname and 'lambda ' in code[lnum]:
            # lambdas
            block = inspect.getblock(code[lnum:])
            lnum += len(block)
            lhs,rhs = block[0].split('lambda ',1)[-1].split(":", 1) #FIXME: bad
            try: #FIXME: unsafe
                _ = eval("lambda %s : %s" % (lhs, rhs), globals(), locals())
            except: _ = lambda : "__this_is_a_big_dummy_function__"
            if PYTHON3: _ = _.__code__
            else: _ = _.func_code
            if _.co_code == ocode.co_code:
                if lstrip: block[0] = block[0].lstrip()
                codeblocks.append(block)
   #            obtypes.append('<lambda>')
        #XXX: would be nice to grab constructor for instance, but yikes.
        else:
            lnum +=1
   #if gettype: return codeblocks, objtypes 
    return codeblocks #XXX: danger... gets methods and closures w/o containers

def getsource(object, alias=''):
    """Extract source code from python code object.

This function is designed to work with simple functions, and will not
work on any general callable. However, this function can extract source
code from functions that are defined interactively.
    """
    import inspect
    _types = ()
    try:
        if PYTHON3:
            ocode = object.__code__
            attr = '__code__'
        else:
            ocode = object.func_code
            attr = 'func_code'
        mname = ocode.co_filename
    except AttributeError:
        try:
            inspect.getmro(object) # ensure it's a class
            mname = inspect.getfile(object)
        except TypeError: # fails b/c class defined in __main__, builtin
            mname = object.__module__
            if mname == '__main__': mname = '<stdin>'
        except AttributeError: # fails b/c it's not a class
            _types = ('<class ',"<type 'instance'>")#,"<type 'module'>")
            if not repr(type(object)).startswith(_types): raise
            mname = getattr(object, '__module__', None)
            if mname == '__main__': mname = '<stdin>'
        attr = '__module__' #XXX: better?
    # no try/except
    if hasattr(object,attr) and mname == '<stdin>':
        # class/function is typed in at the python shell (instance ok)
        lines = getblocks(object, lstrip=True)[-1]
    else:
        try: # get class/functions from file (instances fail)
            lines = inspect.getsourcelines(object)[0]
            # remove indentation from first line
            lines[0] = lines[0].lstrip()
        except TypeError: # failed to get source, resort to import hooks
            if _types: name = object.__class__.__name__
            else: name = object.__name__
           #module = object.__module__.replace('__builtin__','__builtins__')
            module = object.__module__
            if module in ['__builtin__','__builtins__']:
                lines = ["%s = %s\n" % (name, name)]
            else:
                lines = ["%s = __import__('%s', fromlist=['%s']).%s\n" % (name,module,name,name)]
            if _types: # we now go for the class source
                obj = eval(lines[0].lstrip(name + ' = '))
                lines = inspect.getsourcelines(obj)[0]
                lines[0] = lines[0].lstrip()
    if _types: # instantiate, if there's a nice repr  #XXX: BAD IDEA???
        if '(' in repr(object): lines.append('\n_ = %s\n' % repr(object))
        else: object.__code__ # raise AttributeError
    if alias:
        if attr != '__module__':
            if lines[0].startswith('def '): # we have a function
                lines.append('\n%s = %s\n' % (alias, object.__name__))
            elif 'lambda ' in lines[0]: # we have a lambda
                lines[0] = '%s = %s' % (alias, lines[0])
            else: # ...try to use the object's name
                lines.append('\n%s = %s\n' % (alias, object.__name__))
        else: # class or class instance
            if _types: lines.append('%s = _\n' % alias)
            else: lines.append('\n%s = %s\n' % (alias, object.__name__))
    return ''.join(lines)

#exec_ = lambda s, *a: eval(compile(s, '<string>', 'exec'), *a)
__globals__ = globals()
__locals__ = locals()
wrap2 = '''
def _wrap(f):
    """ encapsulate a function and it's __import__ """
    def func(*args, **kwds):
        try:
            #_ = eval(getsource(f)) #FIXME: safer, but not as robust
            exec getimportable(f, alias='_') in %s, %s
        except:
            raise ImportError('cannot import name ' + f.__name__)
        return _(*args, **kwds)
    func.__name__ = f.__name__
    func.__doc__ = f.__doc__
    return func
''' % ('__globals__', '__locals__')
wrap3 = '''
def _wrap(f):
    """ encapsulate a function and it's __import__ """
    def func(*args, **kwds):
        try:
            #_ = eval(getsource(f)) #FIXME: safer, but not as robust
            exec(getimportable(f, alias='_'), %s, %s)
        except:
            raise ImportError('cannot import name ' + f.__name__)
        return _(*args, **kwds)
    func.__name__ = f.__name__
    func.__doc__ = f.__doc__
    return func
''' % ('__globals__', '__locals__')
if PYTHON3:
    exec(wrap3)
else:
    exec(wrap2)
del wrap2, wrap3

def getname(obj): #XXX: too simple... pull in logic from getimportable, etc ?
    """ get the name of the object. for lambdas, get the name of the pointer """
    if obj.__name__ == '<lambda>':
        return getsource(obj).split('=',1)[0].strip()
    return obj.__name__

def _namespace(obj):
    """_namespace(obj); return namespace hierarchy (as a list of names)
    for the given object.

    For example:

    >>> from functools import partial
    >>> p = partial(int, base=2)
    >>> _namespace(p)
    [\'functools\', \'partial\']
    """
    # mostly for functions and modules and such
    try: #FIXME: this function needs some work and testing on different types
        from inspect import getmodule, ismodule
        qual = str(getmodule(obj)).split()[1].strip('"').strip("'")
        qual = qual.split('.')
        if ismodule(obj):
            return qual
        try: # special case: get the name of a lambda
            name = getname(obj)
        except: #XXX: fails to get name
            name = obj.__name__
        return qual + [name] #XXX: can be wrong for some aliased objects
    except: pass
    # special case: numpy.inf and numpy.nan (we don't want them as floats)
    if str(obj) in ['inf','nan','Inf','NaN']: # is more, but are they needed?
        return ['numpy'] + [str(obj)]
    # mostly for classes and class instances and such
    module = getattr(obj.__class__, '__module__', None)
    qual = str(obj.__class__)
    try: qual = qual[qual.index("'")+1:-2]
    except ValueError: pass # str(obj.__class__) made the 'try' unnecessary
    qual = qual.split(".")
    if module in ['builtins', '__builtin__']:
        qual = [module] + qual
    return qual

def _likely_import(first, last, passive=False, explicit=False):
    """build a likely import string"""
    # we don't need to import from builtins, so return ''
    if last in ['NoneType','int','float','long','complex']: return ''#XXX: more
    if not explicit and first in ['builtins','__builtin__']: return ''
    # get likely import string
    if not first: _str = "import %s\n" % last
    else: _str = "from %s import %s\n" % (first, last)
    # FIXME: breaks on most decorators, currying, and such...
    #        (could look for magic __wrapped__ or __func__ attr)
    if not passive and not first.startswith('dill.'):# weird behavior for dill
       #print(_str)
        try: exec(_str) #XXX: check if == obj? (name collision)
        except ImportError: #XXX: better top-down or bottom-up recursion?
            _first = first.rsplit(".",1)[0] #(or get all, then compare == obj?)
            if not _first: raise
            if _first != first:
                _str = _likely_import(_first, last, passive)
    return _str

def likely_import(obj, passive=False, explicit=False):
    """get the likely import string for the given object

    obj: the object to inspect
    passive: if True, then don't try to verify with an attempted import
    explicit: if True, then also include imports for builtins
    """
    # for named things... with a nice repr #XXX: move into _namespace?
    if not repr(obj).startswith('<'): name = repr(obj).split('(')[0]
    else: name = None
    # get the namespace
    qual = _namespace(obj)
    first = '.'.join(qual[:-1])
    last = qual[-1]
    if name: # try using name instead of last
        try: return _likely_import(first, name, passive)
        except (ImportError,SyntaxError): pass
    try:
        if type(obj) is type(abs): _explicit = explicit # BuiltinFunctionType
        else: _explicit = False
        return _likely_import(first, last, passive, _explicit)
    except (ImportError,SyntaxError):
        raise # could do some checking against obj


def getimportable(obj, alias='', byname=True, explicit=False):
    """attempt to get an importable string that captures the state of obj

For simple objects, this function will discover the name of the object, or the
repr of the object, or the source code for the object. To attempt to force
discovery of the source code, use byname=False. The intent is to build a
string that can be imported from a python file. Use explicit=True if imports
from builtins need to be included.
    """
   #try: # get the module name (to see if it's __main__)
   #    module = str(getmodule(obj)).split()[1].strip('"').strip("'")
   #except: module = ''
    try: _import = likely_import(obj, explicit=explicit)
    except: _import = ""
    # try to get the name (or source)...
    if repr(obj).startswith('<'):
        if not byname:
            try: # try to get the source for lambdas and such
               #print(result)
                return getsource(obj, alias=alias)
            except: pass # AttributeError: pass
        try: # get the name (of functions and classes)
            obj = getname(obj)
        except: 
            obj = repr(obj)
        #FIXME: what to do about class instances and such?
    # hope that it can be built from the __repr__
    else: obj = repr(obj)
    # we either have __repr__ or __name__
    if obj.startswith('<'):
        raise AttributeError("object has no atribute '__name__'")
    elif alias: result = _import+'%s = %s\n' % (alias,obj)
    elif _import.endswith('%s\n' % obj): result = _import
    else: result = _import+'%s\n' % obj
   #print(result)
    return result
    #XXX: possible failsafe...
    #     "import dill; result = dill.loads(<pickled_object>); # repr(<object>)"


# backward compatability
_get_name = getname
getblocks_from_history = getblocks

del sys


# EOF
