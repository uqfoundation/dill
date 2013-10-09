#!/usr/bin/env python
"""
all Python Standard Library objects (currently: CH 1-14 @ 2.7)
and some other common objects (i.e. numpy.ndarray)
"""

__all__ = ['registered','failures','succeeds']

# helper imports
import warnings; warnings.filterwarnings("ignore", category=DeprecationWarning)
import sets # Deprecated
import re
import array
import collections
import cStringIO
import codecs
import struct
import datetime
import calendar
import mutex
import weakref
import Queue
import pprint
import decimal
import functools
import itertools
import operator
import tempfile
import sqlite3
import bz2
import gzip
import zipfile
import tarfile
import csv
import logging
import threading
import socket
import contextlib

# helper objects
class _class:
    def _method(self):
        pass
#   @classmethod
#   def _clsmethod(cls): #XXX: test me
#       pass
#   @staticmethod
#   def _static(self): #XXX: test me
#       pass
class _class2:
    def __call__(self):
        pass
_instance2 = _class2()
class _newclass(object):
    def _method(self):
        pass
#   @classmethod
#   def _clsmethod(cls): #XXX: test me
#       pass
#   @staticmethod
#   def _static(self): #XXX: test me
#       pass
def _function(x): yield x
def _function2():
    try: raise
    except:
        from sys import exc_info
        e, er, tb = exc_info()
        return er, tb
_filedescrip, _tempfile = tempfile.mkstemp('w') # deleted in cleanup

# objects used by dill for type declaration
registered = d = {}
# objects dill fails to pickle
failures = x = {}
# all other type objects
succeeds = a = {}

# types module (part of CH 8)
a['BooleanType'] = bool(1)
a['BufferType'] = buffer
a['BuiltinFunctionType'] = len
a['BuiltinMethodType'] = a['BuiltinFunctionType']
a['ClassType'] = _class
a['ComplexType'] = complex(1)
a['DictType'] = _dict = {}
a['DictionaryType'] = a['DictType']
a['FileType'] = file
a['FloatType'] = float(1)
a['FunctionType'] = _function
a['InstanceType'] = _instance = _class()
a['IntType'] = int(1)
a['ListType'] = _list = []
a['LongType'] = long(1)
a['NoneType'] = None
a['ObjectType'] = object()
a['StringType'] = str(1)
a['TupleType'] = _tuple = ()
a['TypeType'] = type
a['UnicodeType'] = unicode(1)
# built-in constants (CH 4)
a['CopyrightType'] = copyright
# built-in types (CH 5)
a['ClassObjectType'] = _newclass # <type 'type'>
a['ClassInstanceType'] = _newclass() # <type 'class'>
a['SetType'] = _set = set()
a['FrozenSetType'] = frozenset()
# built-in exceptions (CH 6)
a['ExceptionType'] = _function2()[0]
# string services (CH 7)
a['RegexPatternType'] = _srepattern = re.compile('')
# data types (CH 8)
a['SetsType'] = sets.Set()
a['ImmutableSetType'] = sets.ImmutableSet()
a['ArrayType'] = array.array("f")
a['DequeType'] = collections.deque([0])
a['DefaultDictType'] = collections.defaultdict(_function, _dict)
a['TZInfoType'] = datetime.tzinfo()
a['DateTimeType'] = datetime.datetime.today()
a['CalendarType'] = calendar.Calendar()
a['MutexType'] = mutex.mutex()
# numeric and mathematical types (CH 9)
a['DecimalType'] = decimal.Decimal(1)
a['CountType'] = itertools.count(0)
# data compression and archiving (CH 12)
a['TarInfoType'] = tarfile.TarInfo()
# generic operating system services (CH 15)
a['LoggerType'] = logging.getLogger()

try: # python 2.6
    import fractions
    import number
    # built-in functions (CH 2)
    a['ByteArrayType'] = bytearray([1])
    # numeric and mathematical types (CH 9)
    a['FractionType'] = fractions.Fraction()
    a['NumberType'] = numbers.Number()
except ImportError:
    pass
try: # python 2.7
    # data types (CH 8)
    a['OrderedDictType'] = collections.OrderedDict(_dict)
    a['CounterType'] = collections.Counter(_dict)
except AttributeError:
    pass

# -- pickle fails on all below here -----------------------------------------
# types module (part of CH 8)
a['CodeType'] = compile('','','exec')
a['DictProxyType'] = type.__dict__
a['EllipsisType'] = Ellipsis
a['GetSetDescriptorType'] = array.array.typecode
a['LambdaType'] = _lambda = lambda x: lambda y: x #XXX: works when not imported!
a['MemberDescriptorType'] = type.__dict__['__weakrefoffset__']
a['MemberDescriptorType2'] = datetime.timedelta.days
a['MethodType'] = _method = _class()._method #XXX: works when not imported!
a['ModuleType'] = datetime
a['NotImplementedType'] = NotImplemented
a['SliceType'] = slice(1)
a['UnboundMethodType'] = _class._method #XXX: works when not imported!
a['XRangeType'] = _xrange = xrange(1)
# other (concrete) object types
a['CellType'] = (_lambda)(0).func_closure[0]
a['MethodDescriptorType'] = type.__dict__['mro']
a['WrapperDescriptorType'] = type.__repr__
a['WrapperDescriptorType2'] = type.__dict__['__module__']
# built-in functions (CH 2)
a['MethodWrapperType'] = [].__repr__
a['StaticMethodType'] = staticmethod(_method)
a['ClassMethodType'] = classmethod(_method)
a['PropertyType'] = property()
a['SuperType'] = super(type)
# data types (CH 8)
a['QueueType'] = Queue.Queue()
a['PrettyPrinterType'] = pprint.PrettyPrinter()
# numeric and mathematical types (CH 9)
a['PartialType'] = functools.partial(int,base=2)
a['IzipType'] = itertools.izip('0','1')
a['ChainType'] = itertools.chain('0','1')
# file and directory access (CH 10)
a['TemporaryFileType'] = _file2 = tempfile.TemporaryFile('w')
# data persistence (CH 11)
a['ConnectionType'] = _conn = sqlite3.connect(':memory:')
a['CursorType'] = _conn.cursor()
# data compression and archiving (CH 12)
a['BZ2FileType'] = bz2.BZ2File(_tempfile)
a['BZ2CompressorType'] = bz2.BZ2Compressor()
a['BZ2DecompressorType'] = bz2.BZ2Decompressor()
# a['ZipFileType'] = _zip = zipfile.ZipFile(_tempfile,'w')
# _zip.write(_tempfile,'x') # FIXME: pickling throws weird error
# a['ZipInfoType'] = _zip.getinfo('x')
a['TarFileType'] = tarfile.open(fileobj=_file2,mode='w')
# file formats (CH 13)
a['DialectType'] = csv.get_dialect('excel')
# optional operating system services (CH 16)
a['LockType'] = threading.Lock()
a['RLockType'] = threading.RLock()
# generic operating system services (CH 15)
a['NamedLoggerType'] = logging.getLogger(__name__)
# interprocess communication (CH 17)
a['SocketType'] = _socket = socket.socket()
a['SocketPairType'] = _socket._sock
# python runtime services (CH 27)
a['GeneratorContextManagerType'] = contextlib.GeneratorContextManager(max)

try: # ipython
    __IPYTHON__ is True # is ipython
except NameError:
    # built-in constants (CH 4)
    a['QuitterType'] = quit
    a['ExitType'] = a['QuitterType']
try: # numpy
    from numpy import ufunc as _numpy_ufunc
    from numpy import array as _numpy_array
    from numpy import int32 as _numpy_int32
    a['NumpyUfuncType'] = _numpy_ufunc
    a['NumpyArrayType'] = _numpy_array
    a['NumpyInt32Type'] = _numpy_int32
except ImportError:
    pass
try: # python 2.6
    # numeric and mathematical types (CH 9)
    a['ProductType'] = itertools.product('0','1')
except AttributeError:
    pass

# -- dill fails in 2.5/2.6 below here ---------------------------------------
x['GzipFileType'] = gzip.GzipFile(fileobj=_file2)
# -- dill fails on all below here -------------------------------------------
# types module (part of CH 8)
x['DictProxyType2'] = _newclass.__dict__
x['GeneratorType'] = _generator = _function(1) #XXX: priority
x['FrameType'] = _generator.gi_frame #XXX: inspect.currentframe()
x['TracebackType'] = _function2()[1] #(see: inspect.getouterframes,getframeinfo)
# other (concrete) object types
# (also: Capsule, CObject, ...?)
# built-in functions (CH 2)
x['ListIteratorType'] = iter(_list) #XXX: empty vs non-empty
x['TupleIteratorType']= iter(_tuple) #XXX: empty vs non-empty
x['XRangeIteratorType'] = iter(_xrange) #XXX: empty vs non-empty
x['SetIteratorType'] = iter(_set) #XXX: empty vs non-empty
# built-in types (CH 5)
x['DictionaryItemIteratorType'] = type.__dict__.iteritems()
x['DictionaryKeyIteratorType'] = type.__dict__.iterkeys()
x['DictionaryValueIteratorType'] = type.__dict__.itervalues()
# string services (CH 7)
# x['InputType'] = cStringIO.InputType #FIXME: write me #XXX: priority
# x['OutputType'] = cStringIO.OutputType # FIXME: write me #XXX: priority
x['StructType'] = struct.Struct('c')
##_callableiter = _srepattern.finditer('')
##_srematch = _srepattern.match('')
##_srescanner = _srepattern.scanner('')
##_streamreader = codecs.StreamReader(_file2) # etc
# data types (CH 8)
x['ReferenceType'] = weakref.ref(_instance) #XXX: priority
# x['DeadReferenceType'] = weakref.ref(_class())
x['ProxyType'] = weakref.proxy(_instance) #XXX: priority
# x['DeadProxyType'] = weakref.proxy(_class())
x['CallableProxyType'] = weakref.proxy(_instance2) #XXX: priority
# x['DeadCallableProxyType'] = weakref.proxy(_class2())
x['WeakKeyDictionaryType'] = weakref.WeakKeyDictionary()
x['WeakValueDictionaryType'] = weakref.WeakValueDictionary()
# numeric and mathematical types (CH 9)
x['CycleType'] = itertools.cycle('0')
x['ItemGetterType'] = operator.itemgetter(0)
x['AttrGetterType'] = operator.attrgetter('__repr__')
# python object persistence (CH 11)
##import shelve; _shelve = shelve.Shelf({})
##import dbm; _dbm = dbm.open('foo','n')
##import anydbm; _dbcursor = anydbm.open('foo','n')
##_db = _dbcursor.db
# data compression and archiving (CH 12)
##import zlib; _zcompress = zlib.compressobj()
##_zdecompress = zlib.decompressobj()
# file formats (CH 13)
##_csvreader = csv.reader(_file2)
##_csvwriter = csv.writer(_file2)
##_csvdreader = csv.DictReader(_file2)
##_csvdwriter = csv.DictWriter(_file2,{})
##import xdrlib; _xdr = xdrlib.Packer()
# cryptographic services (CH 14)
##import hashlib; _hash = hashlib.md5()
##import hmac; _hmac = hmac.new('')

try: # python 2.6
    # numeric and mathematical types (CH 9)
    x['PermutationsType'] = itertools.permutations('0')
    x['CombinationsType'] = itertools.combinations('0',1)
    x['MethodCallerType'] = operator.methodcaller('mro') # 2.6
except AttributeError:
    pass
try: # python 2.7
    ##import locale
    # built-in types (CH 5)
    x['DictItemsType'] = _dict.viewitems() # 2.7
    x['DictKeysType'] = _dict.viewkeys() # 2.7
    x['DictValuesType'] = _dict.viewvalues() # 2.7
    x['MemoryType'] = memoryview('0') # 2.7
    x['MemoryType2'] = memoryview(bytearray('0')) # 2.7
    # data types (CH 8)
    x['WeakSetType'] = weakref.WeakSet() # 2.7
    # numeric and mathematical types (CH 9)
    x['RepeatType'] = itertools.repeat(0) # 2.7
    x['CompressType'] = itertools.compress('0',[1]) #XXX: ...and etc
    ##_cmpkey = functools.cmp_to_key(locale.strcoll) # 2.7
    ##_cmpkeyobj = _cmpkey('0') #2.7
except AttributeError:
    pass

# -- cleanup ----------------------------------------------------------------
import os; os.remove(_tempfile)


# EOF
