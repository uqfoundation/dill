#!/usr/bin/env python

import dill as pickle
#import pickle

typelist = []

# testing types
_none = None; typelist.append(_none)
_type = type; typelist.append(_type)
_bool = bool(1); typelist.append(_bool)
_int = int(1); typelist.append(_int)
_long = long(1); typelist.append(_long)
_float = float(1); typelist.append(_float)
_complex = complex(1); typelist.append(_complex)
_string = str(1); typelist.append(_string)
_unicode = unicode(1); typelist.append(_unicode)
_tuple = (); typelist.append(_tuple)
_list = []; typelist.append(_list)
_dict = {}; typelist.append(_dict)
_file = file; typelist.append(_file)
_buffer = buffer; typelist.append(_buffer)
_builtin = len; typelist.append(_builtin)
class _class:
    def _method(self):
        pass
class _newclass(object):
    def _method(self):
        pass
typelist.append(_class)
typelist.append(_newclass) # <type 'type'>
_instance = _class(); typelist.append(_instance)
_object = _newclass(); typelist.append(_object) # <type 'class'>
def _function(x): yield x; typelist.append(_function)
_lambda = lambda x: lambda y: x; typelist.append(_lambda) # pickle fails
_cell = (_lambda)(0).func_closure[0]; typelist.append(_cell) # pickle fails
_method = _class()._method; typelist.append(_method) # pickle fails
_ubmethod = _class._method; typelist.append(_ubmethod) # pickle fails
_module = pickle; typelist.append(_module) # pickle fails
_code = compile('','','exec'); typelist.append(_code) # pickle fails
import array; _getsetdescrip = array.array.typecode; typelist.append(_getsetdescrip) # pickle fails
#_generator = _function(1); typelist.append(_generator) # pickle fails #XXX: FAILS
#_dictproxy = type.__dict__; typelist.append(_dictproxy) # pickle fails #XXX: FAILS
#_xrange = xrange(1); typelist.append(_xrange) # pickle fails #XXX: FAILS
#_slice = slice(1); typelist.append(_slice) # pickle fails #XXX: FAILS
#_nimp = NotImplemented; typelist.append(_nimp) # pickle fails #XXX: FAILS
#_ellipsis = Ellipsis; typelist.append(_ellipsis) # pickle fails #XXX: FAILS
#import datetime; _membdescrip = datetime.timedelta.days; typelist.append(_membdescrip) # pickle fails #XXX: FAILS
#---------------
#_traceback = ???
#_frame = ???


if __name__ == '__main__':

  for member in typelist:
      p = pickle.dumps(member)
      _member = pickle.loads(p)

