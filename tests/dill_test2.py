#!/usr/bin/env python
"""
demonstrate dill's ability to pickle different python types
"""

import dill as pickle
#pickle._trace(True)
#import pickle

typelist = []
import warnings; warnings.filterwarnings("ignore", category=DeprecationWarning)

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
_object2 = object(); typelist.append(_object2)
_set = set(); typelist.append(_set)
_frozenset = frozenset(); typelist.append(_frozenset)
import sets; _set2 = sets.Set(); typelist.append(_set2)  # Deprecated
_immutableset = sets.ImmutableSet(); typelist.append(_immutableset)
import array; _array = array.array("f"); typelist.append(_array)
def _function2():
    try: raise
    except:
      from sys import exc_info
      e, er, tb = exc_info()
      return er, tb
_exception = _function2()[0]; typelist.append(_exception)
import decimal; _decimal = decimal.Decimal(1); typelist.append(_decimal)
_copyright = copyright; typelist.append(_copyright)
def _function(x): yield x; typelist.append(_function)
import logging; _logger = logging.getLogger(); typelist.append(_logger)
import re; _srepattern = re.compile(''); typelist.append(_srepattern)
import collections; _deque = collections.deque([0]); typelist.append(_deque)
_ddict = collections.defaultdict(_function, _dict); typelist.append(_ddict)
import datetime; _tzinfo = datetime.tzinfo(); typelist.append(_tzinfo)
_datetime = datetime.datetime.today(); typelist.append(_datetime)
import calendar; _calendar = calendar.Calendar(); typelist.append(_calendar)
import mutex; _mutex = mutex.mutex(); typelist.append(_mutex)
import itertools; _count = itertools.count(0); typelist.append(_count)
import tarfile; _tinfo = tarfile.TarInfo(); typelist.append(_tinfo)
try: # python 2.6
  import fractions; _fraction = fractions.Fraction(); typelist.append(_fraction)
  import number; _number = numbers.Number(); typelist.append(_number)
  _bytearray = bytearray([1]); typelist.append(_bytearray)
except ImportError:
  pass
try: # python 2.7
  _odict = collections.OrderedDict(_dict); typelist.append(_odict) # 2.7
  _counter = collections.Counter(_dict); typelist.append(_counter) # 2.7
except AttributeError:
  pass
# pickle fails on all below here -------------------------------------------
_lambda = lambda x: lambda y: x; typelist.append(_lambda)
_cell = (_lambda)(0).func_closure[0]; typelist.append(_cell)
_method = _class()._method; typelist.append(_method)
_ubmethod = _class._method; typelist.append(_ubmethod)
_module = pickle; typelist.append(_module)
_code = compile('','','exec'); typelist.append(_code)
_dictproxy = type.__dict__; typelist.append(_dictproxy)
_dictprox2 = _newclass.__dict__; typelist.append(_dictprox2)
_methoddescr = type.__dict__['mro']; typelist.append(_methoddescr)
_memdescr = datetime.timedelta.days; typelist.append(_memdescr)
_memdescr2 = type.__dict__['__weakrefoffset__']; typelist.append(_memdescr2)
import array; _getsetdescr = array.array.typecode; typelist.append(_getsetdescr)
_wrapperdescr = type.__repr__; typelist.append(_wrapperdescr)
_wrapperdescr2 = type.__dict__['__module__']; typelist.append(_wrapperdescr2)
_xrange = xrange(1); typelist.append(_xrange)
_slice = slice(1); typelist.append(_slice)
_nimp = NotImplemented; typelist.append(_nimp)
_ellipsis = Ellipsis; typelist.append(_ellipsis)
_staticmethod = staticmethod(_method); typelist.append(_staticmethod)
_classmethod = classmethod(_method); typelist.append(_classmethod)
_property = property(); typelist.append(_property)
_super = super(type); typelist.append(_super)
_izip = itertools.izip('0','1'); typelist.append(_izip)
_chain = itertools.chain('0','1'); typelist.append(_chain)
import sqlite3; _conn = sqlite3.connect(':memory:'); typelist.append(_conn)
_cursor = _conn.cursor(); typelist.append(_cursor)
import tempfile; _file2 = tempfile.TemporaryFile('w'); typelist.append(_file2)
_filedescrip, _tempfile = tempfile.mkstemp('w') # used for pickle-testing
import bz2; _bz2 = bz2.BZ2File(_tempfile); typelist.append(_bz2)
_bz2compress = bz2.BZ2Compressor(); typelist.append(_bz2compress)
_bz2decompress = bz2.BZ2Decompressor(); typelist.append(_bz2decompress)
#import zipfile; _zip = zipfile.ZipFile(_tempfile,'w'); typelist.append(_zip)
#_zip.write(_tempfile,'x'); _zinfo = _zip.getinfo('x'); typelist.append(_zinfo)
_tar = tarfile.open(fileobj=_file2,mode='w'); typelist.append(_tar)
import csv; _dialect = csv.get_dialect('excel'); typelist.append(_dialect)
import pprint; _printer = pprint.PrettyPrinter(); typelist.append(_printer)
import socket; _socket = socket.socket(); typelist.append(_socket)
import contextlib; _ctxmgr = contextlib.GeneratorContextManager(max); typelist.append(_ctxmgr)
try:
  __IPYTHON__ is True # is ipython
except NameError:
  _quitter = quit; typelist.append(_quitter)
try:
  from numpy import ufunc as _numpy_ufunc
  typelist.append(_numpy_ufunc)
  from numpy import array as _numpy_array
  typelist.append(_numpy_array)
  from numpy import int32 as _numpy_int32
  typelist.append(_numpy_int32)
except ImportError:
  pass
try: # python 2.6
  _product = itertools.product('0','1'); typelist.append(_product)
except AttributeError:
  pass
# dill fails in 2.5/2.6 below here -------------------------------------------
#import gzip; _gzip = gzip.GzipFile(fileobj=_file2); typelist.append(_gzip)
#import functools; _part = functools.partial(int,base=2); typelist.append(_part)
# dill fails on all below here -------------------------------------------
_traceback = _function2()[1]; typelist.append(_traceback)
_generator = _function(1); typelist.append(_generator)
_frame = _generator.gi_frame; typelist.append(_frame)
#_socketpair = _socket._sock
##_logger2 = logging.getLogger(__name__)
##import thread; _lock = thread.allocate()
##import Queue; _queue = Queue.Queue()
##_methodwrapper = (1).__repr__
##_listiter = iter(_list)
##_tupleiter = iter(_tuple)
##_xrangeiter = iter(_xrange)
##_setiter = iter(_set)
##_cycle = itertools.cycle('0')
##_repeat = itertools.repeat(0) # 2.7
##_compress = itertools.compress('0',[1]) # etc
##_permute = itertools.permutations('0')
##_combine = itertools.combinations('0',1)
##_dictitemiter = type.__dict__.iteritems()
##_dictkeyiter = type.__dict__.iterkeys()
##_dictvaliter = type.__dict__.itervalues()
##_dictitems = _dict.viewitems() # 2.7
##_dictkeys = _dict.viewkeys() # 2.7
##_dictvalues = _dict.viewvalues() # 2.7
##_memory = memoryview('0') # 2.7
##_memory2 = memoryview(bytearray('0')) # 2.7
##import cStringIO; _stringi = cStringIO.InputType
##_stringo = cStringIO.OutputType
##import operator; _itemgetter = operator.itemgetter(0)
##_attrgetter = operator.attrgetter('__repr__')
##_methodcall = operator.methodcaller('mro') # 2.6
##import struct; _struct = struct.Struct('c')
import weakref; _ref = weakref.ref(_instance); typelist.append(_ref)
##_deadref = weakref.ref(_class()); typelist.append(_deadref)
#_proxy = weakref.proxy(_instance); typelist.append(_proxy)
##_deadproxy = weakref.proxy(_class()); typelist.append(_deadproxy)
class _class2:
    def __call__(self):
        pass
_instance2 = _class2()
#_callable = weakref.proxy(_instance2); typelist.append(_callable)
##_deadcallable = weakref.proxy(_class2()); typelist.append(_deadcallable)
##_weakset = weakref.WeakSet(); typelist.append(_weakset) # 2.7
##_weakkeydict = weakref.WeakKeyDictionary(); typelist.append(_weakkeydict)
##_weakvaldict = weakref.WeakValueDictionary(); typelist.append(_weakvaldict)
##_callableiter = _srepattern.finditer(''); typelist.append(_callableiter)
##_srematch = _srepattern.match(''); typelist.append(_srematch)
##_srescanner = _srepattern.scanner(''); typelist.append(_srescanner)
##import codecs; _streamreader = codecs.StreamReader(_file2) # etc
##import locale; _cmpkey = functools.cmp_to_key(locale.strcoll) # 2.7
##_cmpkeyobj = _cmpkey('0') #2.7
##import shelve; _shelve = shelve.Shelf({})
##import dbm; _dbm = dbm.open('foo','n')
##import anydbm; _dbcursor = anydbm.open('foo','n')
##_db = _dbcursor.db
##import zlib; _zcompress = zlib.compressobj()
##_zdecompress = zlib.decompressobj()
##_csvreader = csv.reader(_file2)
##_csvwriter = csv.writer(_file2)
##_csvdreader = csv.DictReader(_file2)
##_csvdwriter = csv.DictWriter(_file2,{})
##import xdrlib; _xdr = xdrlib.Packer()
##import hashlib; _hash = hashlib.md5()
##import hmac; _hmac = hmac.new('')
# cleanup -------------------------------------------
import os; os.remove(_tempfile)


if __name__ == '__main__':

  def pickles(x):
    #print type(x)
    try:
      p = pickle.loads(pickle.dumps(x))
      try:
        assert x == p
      except AssertionError, err:
        assert type(x) == type(p)
        print "weak: %s" % type(x)
    except (TypeError, pickle.PicklingError), err:
      print "COPY failure: %s" % type(x)
    return

  for member in typelist:
     #print "%s ==> %s" % (member, type(member)) # DEBUG
      pickles(member)
  for member in typelist:
     #print "%s ==> %s" % (member, type(member)) # DEBUG
      try:
          pickle.loads(pickle.dumps(member))
      except:
          print "PICKLE failure: %s" % type(member)

