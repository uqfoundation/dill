#!/usr/bin/env python

"""
Extensions to python's 'inspect' module, which can be used
to retrieve information from live python objects. The primary
target of 'dill.source' is to facilitate access to the source
code of interactively defined functions and classes.
"""

def getblocks_from_history(object, lstrip=False):# gettype=False):
    """extract code blocks from a code object using stored history"""
    import readline, inspect, types
    lbuf = readline.get_current_history_length()
    code = [readline.get_history_item(i)+'\n' for i in range(1,lbuf)]
    lnum = 0
    codeblocks = []
   #objtypes = []
    while lnum < len(code):#-1:
       if code[lnum].lstrip().startswith('def '):
           block = inspect.getblock(code[lnum:])
           lnum += len(block)
           if block[0].lstrip().startswith('def %s(' % object.func_name):
               if lstrip: block[0] = block[0].lstrip()
               codeblocks.append(block)
   #           obtypes.append(types.FunctionType)
       elif 'lambda ' in code[lnum]:
           block = inspect.getblock(code[lnum:])
           lnum += len(block)
           lhs,rhs = block[0].split('lambda ',1)[-1].split(":", 1) #FIXME: bad
           try: #FIXME: unsafe
               _ = eval("lambda %s : %s" % (lhs, rhs), globals(), locals())
           except: pass
           if _.func_code.co_code == object.func_code.co_code:
               if lstrip: block[0] = block[0].lstrip()
               codeblocks.append(block)
   #           obtypes.append('<lambda>')
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
    # no try/except
    if hasattr(object,'func_code') and object.func_code.co_filename == '<stdin>':
        # function is typed in at the python shell
        lines = getblocks_from_history(object, lstrip=True)[-1]
    else:
        try:
            lines = inspect.getsourcelines(object)[0]
            # remove indentation from first line
            lines[0] = lines[0].lstrip()
        except TypeError: # failed to get source, resort to import hooks
            name = object.__name__
           #module = object.__module__.replace('__builtin__','__builtins__')
            module = object.__module__
            if module in ['__builtin__','__builtins__']:
                lines = ["%s = %s\n" % (name, name)]
            else:
                lines = ["%s = __import__('%s', fromlist=['%s']).%s\n" % (name,module,name,name)]
    if alias:
        if lines[0].startswith('def '): # we have a function
            lines.append('\n%s = %s\n' % (alias, object.__name__))
        elif 'lambda ' in lines[0]: # we have a lambda
            lines[0] = '%s = %s' % (alias, lines[0])
        else: # ...try to use the object's name
            lines.append('\n%s = %s\n' % (alias, object.__name__))
    return ''.join(lines)

def _wrap(f):
    """ encapsulate a function and it's __import__ """
    def func(*args, **kwds):
        try:
            #_ = eval(getsource(f)) #FIXME: safer, but not as robust
            exec getsource(f, alias='_') in globals(), locals()
        except:
            raise ImportError, "cannot import name %s" % f.__name__
        return _(*args, **kwds)
    func.__name__ = f.__name__
    func.__doc__ = f.__doc__
    return func

def _get_name(obj):
    """ get the name of the object. for lambdas, get the name of the pointer """
    if obj.__name__ == '<lambda>':
        return getsource(obj).split('=',1)[0].strip()
    return obj.__name__


# EOF
