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
try:
    import cStringIO # has StringI and StringO types
except ImportError:
    import StringIO as cStringIO # has StringIO type
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
import shelve
import dbm
import anydbm
import sqlite3
import zlib
import bz2
import gzip
import zipfile
import tarfile
import xdrlib
import csv
import hashlib
import hmac
import os
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
_filedescrip, _tempfile = tempfile.mkstemp('r') # deleted in cleanup

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
a['ExceptionType'] = _exception = _function2()[0]
# string services (CH 7)
a['SREPatternType'] = _srepattern = re.compile('')
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
a['DictProxyType2'] = _newclass.__dict__
a['EllipsisType'] = Ellipsis
a['FileType'] = _fileR = open(os.devnull,'r')
a['ClosedFileType'] = open(os.devnull, 'w').close()
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
d['CellType'] = (_lambda)(0).func_closure[0]
d['MethodDescriptorType'] = type.__dict__['mro']
d['WrapperDescriptorType'] = type.__repr__
a['WrapperDescriptorType2'] = type.__dict__['__module__']
# built-in functions (CH 2)
d['MethodWrapperType'] = [].__repr__
a['StaticMethodType'] = staticmethod(_method)
a['ClassMethodType'] = classmethod(_method)
a['PropertyType'] = property()
d['SuperType'] = super(Exception, _exception)
# string services (CH 7)
a['InputType'] = _cstrI = cStringIO.StringIO('')
a['OutputType'] = _cstrO = cStringIO.StringIO()
# data types (CH 8)
a['ReferenceType'] = weakref.ref(_instance)
a['DeadReferenceType'] = weakref.ref(_class())
a['ProxyType'] = weakref.proxy(_instance)
a['DeadProxyType'] = weakref.proxy(_class())
a['CallableProxyType'] = weakref.proxy(_instance2)
a['DeadCallableProxyType'] = weakref.proxy(_class2())
a['QueueType'] = Queue.Queue()
a['PrettyPrinterType'] = pprint.PrettyPrinter()
# numeric and mathematical types (CH 9)
d['PartialType'] = functools.partial(int,base=2)
a['IzipType'] = itertools.izip('0','1')
a['ChainType'] = itertools.chain('0','1')
d['ItemGetterType'] = operator.itemgetter(0)
d['AttrGetterType'] = operator.attrgetter('__repr__')
# file and directory access (CH 10)
a['TemporaryFileType'] = _fileW = tempfile.TemporaryFile('w')
# data persistence (CH 11)
a['ConnectionType'] = _conn = sqlite3.connect(':memory:')
a['CursorType'] = _conn.cursor()
a['ShelveType'] = shelve.Shelf({})
# data compression and archiving (CH 12)
a['BZ2FileType'] = bz2.BZ2File(os.devnull)
a['BZ2CompressorType'] = bz2.BZ2Compressor()
a['BZ2DecompressorType'] = bz2.BZ2Decompressor()
a['ZipFileType'] = _zip = zipfile.ZipFile(os.devnull,'w')
_zip.write(_tempfile,'x')
a['ZipInfoType'] = _zip.getinfo('x')
a['TarFileType'] = tarfile.open(fileobj=_fileW,mode='w')
# file formats (CH 13)
a['DialectType'] = csv.get_dialect('excel')
a['PackerType'] = xdrlib.Packer()
# optional operating system services (CH 16)
a['LockType'] = threading.Lock()
a['RLockType'] = threading.RLock()
# generic operating system services (CH 15) # also closed/open and r/w/etc...
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
    d['ExitType'] = a['QuitterType']
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
x['GzipFileType'] = gzip.GzipFile(fileobj=_fileW)
# -- dill fails on all below here -------------------------------------------
# types module (part of CH 8)
x['GeneratorType'] = _generator = _function(1) #XXX: priority
x['FrameType'] = _generator.gi_frame #XXX: inspect.currentframe()
x['TracebackType'] = _function2()[1] #(see: inspect.getouterframes,getframeinfo)
# other (concrete) object types
# (also: Capsule / CObject ?)
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
x['StructType'] = struct.Struct('c')
x['CallableIteratorType'] = _srepattern.finditer('')
x['SREMatchType'] = _srepattern.match('')
x['SREScannerType'] = _srepattern.scanner('')
x['StreamReader'] = codecs.StreamReader(_cstrI) #XXX: ... and etc
# data types (CH 8)
x['WeakKeyDictionaryType'] = weakref.WeakKeyDictionary()
x['WeakValueDictionaryType'] = weakref.WeakValueDictionary()
# numeric and mathematical types (CH 9)
x['CycleType'] = itertools.cycle('0')
# python object persistence (CH 11)
# x['DbShelveType'] = shelve.open('foo','n')#,protocol=2) #XXX: delete foo
x['DbmType'] = dbm.open(_tempfile,'n')
# x['DbCursorType'] = _dbcursor = anydbm.open('foo','n') #XXX: delete foo
# x['DbType'] = _dbcursor.db
# data compression and archiving (CH 12)
x['ZlibCompressType'] = zlib.compressobj()
x['ZlibDecompressType'] = zlib.decompressobj()
# file formats (CH 13)
x['CSVReaderType'] = csv.reader(_cstrI)
x['CSVWriterType'] = csv.writer(_cstrO)
x['CSVDictReaderType'] = csv.DictReader(_cstrI)
x['CSVDictWriterType'] = csv.DictWriter(_cstrO,{})
# cryptographic services (CH 14)
x['HashType'] = hashlib.md5()
x['HMACType'] = hmac.new('')

try: # python 2.6
    # numeric and mathematical types (CH 9)
    x['PermutationsType'] = itertools.permutations('0')
    x['CombinationsType'] = itertools.combinations('0',1)
    x['MethodCallerType'] = operator.methodcaller('mro') # 2.6
except AttributeError:
    pass
try: # python 2.7
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
    x['CmpKeyType'] = _cmpkey = functools.cmp_to_key((1).__cmp__) # 2.7
    x['CmpKeyObjType'] = _cmpkey('0') #2.7
except AttributeError:
    pass

# -- cleanup ----------------------------------------------------------------
a.update(d) # registered also succeed
os.remove(_tempfile)


# EOF
