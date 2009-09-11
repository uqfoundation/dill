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
# pickle fails on all below here -------------------------------------------
_lambda = lambda x: lambda y: x; typelist.append(_lambda)
_cell = (_lambda)(0).func_closure[0]; typelist.append(_cell)
_method = _class()._method; typelist.append(_method)
_ubmethod = _class._method; typelist.append(_ubmethod)
_module = pickle; typelist.append(_module)
_code = compile('','','exec'); typelist.append(_code)
_dictproxy = type.__dict__; typelist.append(_dictproxy)
_methoddescrip = _dictproxy['mro']; typelist.append(_methoddescrip)
import array; _getsetdescrip = array.array.typecode; typelist.append(_getsetdescrip)
import datetime; _membdescrip = datetime.timedelta.days; typelist.append(_membdescrip)
_wrapperdescrip = type.__repr__; typelist.append(_wrapperdescrip)
_generator = _function(1); typelist.append(_generator)
_frame = _generator.gi_frame; typelist.append(_frame)
_xrange = xrange(1); typelist.append(_xrange)
_slice = slice(1); typelist.append(_slice)
_nimp = NotImplemented; typelist.append(_nimp)
_ellipsis = Ellipsis; typelist.append(_ellipsis)
#---------------
#_traceback = ???
#---------------
#_reference = ???
#_proxy = ???
#_callable = ???


if __name__ == '__main__':

  for member in typelist:
      if not pickle.pickles(member):
          print "COPY failure: %s" % type(member)
  for member in typelist:
      try: pickle.copy(member)
      except:
          print "PICKLE failure: %s" % type(member)

