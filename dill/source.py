#!/usr/bin/env python

"""
Extensions to python's 'inspect' module, which can be used
to retrieve information from live python objects. The primary
target of 'dill.source' is to facilitate access to the source
code of interactively defined functions and classes.
"""

def getblocks_from_history(object):
    """extract code blocks from a code object using stored history"""
    import readline, inspect
    lbuf = readline.get_current_history_length()
    code = [readline.get_history_item(i)+'\n' for i in range(1,lbuf)]
    lnum = 0
    codeblocks = []
    while lnum < len(code)-1:
       if code[lnum].startswith('def'):    
           block = inspect.getblock(code[lnum:])
           lnum += len(block)
           if block[0].startswith('def %s' % object.func_name):
               codeblocks.append(block)
       else:
           lnum +=1
    return codeblocks

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
        lines = getblocks_from_history(object)[-1]
    else:
        lines, lnum = inspect.getsourcelines(object)
    if alias: lines.append('\n%s = %s\n' % (alias, object.__name__))
    return ''.join(lines)


# EOF
