#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2021 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import os
import sys
# drop support for older python
unsupported = None
if sys.version_info < (2, 7):
    unsupported = 'Versions of Python before 2.7 are not supported'
elif (3, 0) <= sys.version_info < (3, 6):
    unsupported = 'Versions of Python before 3.6 are not supported'
if unsupported:
    raise ValueError(unsupported)

# set version numbers
stable_version = '0.3.4'
target_version = '0.3.4'
is_release = stable_version == target_version

# check if easy_install is available
try:
#   import __force_distutils__ #XXX: uncomment to force use of distutills
    from setuptools import setup
    has_setuptools = True
except ImportError:
    from distutils.core import setup
    has_setuptools = False

# generate version number
if os.path.exists('dill/info.py'):
    # is a source distribution, so use existing version
    os.chdir('dill')
    with open('info.py','r') as f:
        f.readline() # header
        this_version = f.readline().split()[-1].strip("'")
    os.chdir('..')
elif stable_version == target_version:
    # we are building a stable release
    this_version = target_version
else:
    # we are building a distribution
    this_version = target_version + '.dev0'
    if is_release:
        from datetime import date
        today = "".join(date.isoformat(date.today()).split('-'))
        this_version += "-" + today

# get the license info
with open('LICENSE') as file:
    license_text = file.read()

# generate the readme text
long_description = \
"""-----------------------------
dill: serialize all of python
-----------------------------

About Dill
==========

``dill`` extends python's ``pickle`` module for serializing and de-serializing
python objects to the majority of the built-in python types. Serialization
is the process of converting an object to a byte stream, and the inverse
of which is converting a byte stream back to a python object hierarchy.

``dill`` provides the user the same interface as the ``pickle`` module, and
also includes some additional features. In addition to pickling python
objects, ``dill`` provides the ability to save the state of an interpreter
session in a single command.  Hence, it would be feasable to save an
interpreter session, close the interpreter, ship the pickled file to
another computer, open a new interpreter, unpickle the session and
thus continue from the 'saved' state of the original interpreter
session.

``dill`` can be used to store python objects to a file, but the primary
usage is to send python objects across the network as a byte stream.
``dill`` is quite flexible, and allows arbitrary user defined classes
and functions to be serialized.  Thus ``dill`` is not intended to be
secure against erroneously or maliciously constructed data. It is
left to the user to decide whether the data they unpickle is from
a trustworthy source.

``dill`` is part of ``pathos``, a python framework for heterogeneous computing.
``dill`` is in active development, so any user feedback, bug reports, comments,
or suggestions are highly appreciated.  A list of issues is located at https://github.com/uqfoundation/dill/issues, with a legacy list maintained at https://uqfoundation.github.io/project/pathos/query.


Major Features
==============

``dill`` can pickle the following standard types:

    - none, type, bool, int, long, float, complex, str, unicode,
    - tuple, list, dict, file, buffer, builtin,
    - both old and new style classes,
    - instances of old and new style classes,
    - set, frozenset, array, functions, exceptions

``dill`` can also pickle more 'exotic' standard types:

    - functions with yields, nested functions, lambdas,
    - cell, method, unboundmethod, module, code, methodwrapper,
    - dictproxy, methoddescriptor, getsetdescriptor, memberdescriptor,
    - wrapperdescriptor, xrange, slice,
    - notimplemented, ellipsis, quit

``dill`` cannot yet pickle these standard types:

    - frame, generator, traceback

``dill`` also provides the capability to:

    - save and load python interpreter sessions
    - save and extract the source code from functions and classes
    - interactively diagnose pickling errors


Current Release
===============

This documentation is for version ``dill-%(thisver)s``.

The latest released version of ``dill`` is available from:

    https://pypi.org/project/dill

``dill`` is distributed under a 3-clause BSD license.

    >>> import dill
    >>> dill.license()


Development Version
===================

You can get the latest development version with all the shiny new features at:

    https://github.com/uqfoundation

If you have a new contribution, please submit a pull request.


Installation
============

``dill`` is packaged to install from source, so you must
download the tarball, unzip, and run the installer::

    [download]
    $ tar -xvzf dill-%(relver)s.tar.gz
    $ cd dill-%(relver)s
    $ python setup py build
    $ python setup py install

You will be warned of any missing dependencies and/or settings
after you run the "build" step above.

Alternately, ``dill`` can be installed with ``pip`` or ``easy_install``::

    $ pip install dill


Requirements
============

``dill`` requires:

    - ``python``, **version == 2.7** or **version >= 3.6**, or ``pypy``

Optional requirements:

    - ``setuptools``, **version >= 0.6**
    - ``pyreadline``, **version >= 1.7.1** (on windows)
    - ``objgraph``, **version >= 1.7.2**


Basic Usage
===========

``dill`` is a drop-in replacement for ``pickle``. Existing code can be
updated to allow complete pickling using::

    >>> import dill as pickle

or::

    >>> from dill import dumps, loads

``dumps`` converts the object to a unique byte string, and ``loads`` performs
the inverse operation::

    >>> squared = lambda x: x**2
    >>> loads(dumps(squared))(3)
    9

There are a number of options to control serialization which are provided
as keyword arguments to several ``dill`` functions:

* with *protocol*, the pickle protocol level can be set. This uses the
  same value as the ``pickle`` module, *HIGHEST_PROTOCOL* or *DEFAULT_PROTOCOL*.
* with *byref=True*, ``dill`` to behave a lot more like pickle with
  certain objects (like modules) pickled by reference as opposed to
  attempting to pickle the object itself.
* with *recurse=True*, objects referred to in the global dictionary are
  recursively traced and pickled, instead of the default behavior of
  attempting to store the entire global dictionary.
* with *fmode*, the contents of the file can be pickled along with the file
  handle, which is useful if the object is being sent over the wire to a
  remote system which does not have the original file on disk. Options are
  *HANDLE_FMODE* for just the handle, *CONTENTS_FMODE* for the file content
  and *FILE_FMODE* for content and handle.
* with *ignore=False*, objects reconstructed with types defined in the
  top-level script environment use the existing type in the environment
  rather than a possibly different reconstructed type.

The default serialization can also be set globally in *dill.settings*.
Thus, we can modify how ``dill`` handles references to the global dictionary
locally or globally::

    >>> import dill.settings
    >>> dumps(absolute) == dumps(absolute, recurse=True)
    False
    >>> dill.settings['recurse'] = True
    >>> dumps(absolute) == dumps(absolute, recurse=True)
    True

``dill`` also includes source code inspection, as an alternate to pickling::

    >>> import dill.source
    >>> print(dill.source.getsource(squared))
    squared = lambda x:x**2

To aid in debugging pickling issues, use *dill.detect* which provides
tools like pickle tracing::

    >>> import dill.detect
    >>> dill.detect.trace(True)
    >>> f = dumps(squared)
    F1: <function <lambda> at 0x108899e18>
    F2: <function _create_function at 0x108db7488>
    # F2
    Co: <code object <lambda> at 0x10866a270, file "<stdin>", line 1>
    F2: <function _create_code at 0x108db7510>
    # F2
    # Co
    D1: <dict object at 0x10862b3f0>
    # D1
    D2: <dict object at 0x108e42ee8>
    # D2
    # F1
    >>> dill.detect.trace(False)

With trace, we see how ``dill`` stored the lambda (``F1``) by first storing
``_create_function``, the underlying code object (``Co``) and ``_create_code``
(which is used to handle code objects), then we handle the reference to
the global dict (``D2``).  A ``#`` marks when the object is actually stored.


More Information
================

Probably the best way to get started is to look at the documentation at
http://dill.rtfd.io. Also see ``dill.tests`` for a set of scripts that
demonstrate how ``dill`` can serialize different python objects. You can
run the test suite with ``python -m dill.tests``. The contents of any
pickle file can be examined with ``undill``.  As ``dill`` conforms to
the ``pickle`` interface, the examples and documentation found at
http://docs.python.org/library/pickle.html also apply to ``dill``
if one will ``import dill as pickle``. The source code is also generally
well documented, so further questions may be resolved by inspecting the
code itself. Please feel free to submit a ticket on github, or ask a
question on stackoverflow (**@Mike McKerns**).
If you would like to share how you use ``dill`` in your work, please send
an email (to **mmckerns at uqfoundation dot org**).


Citation
========

If you use ``dill`` to do research that leads to publication, we ask that you
acknowledge use of ``dill`` by citing the following in your publication::

    M.M. McKerns, L. Strand, T. Sullivan, A. Fang, M.A.G. Aivazis,
    "Building a framework for predictive science", Proceedings of
    the 10th Python in Science Conference, 2011;
    http://arxiv.org/pdf/1202.1056

    Michael McKerns and Michael Aivazis,
    "pathos: a framework for heterogeneous computing", 2010- ;
    https://uqfoundation.github.io/project/pathos

Please see https://uqfoundation.github.io/project/pathos or
http://arxiv.org/pdf/1202.1056 for further information.

""" % {'relver' : stable_version, 'thisver' : this_version}

# write readme file
with open('README', 'w') as file:
    file.write(long_description)

# generate 'info' file contents
def write_info_py(filename='dill/info.py'):
    contents = """# THIS FILE GENERATED FROM SETUP.PY
this_version = '%(this_version)s'
stable_version = '%(stable_version)s'
readme = '''%(long_description)s'''
license = '''%(license_text)s'''
"""
    with open(filename, 'w') as file:
        file.write(contents % {'this_version' : this_version,
                               'stable_version' : stable_version,
                               'long_description' : long_description,
                               'license_text' : license_text })
    return

# write info file
write_info_py()

# build the 'setup' call
setup_code = """
setup(name='dill',
      version='%s',
      description='serialize all of python',
      long_description = '''%s''',
      author = 'Mike McKerns',
      maintainer = 'Mike McKerns',
      license = '3-clause BSD',
      platforms = ['Linux', 'Windows', 'Mac'],
      url = 'https://github.com/uqfoundation/dill',
      download_url = 'https://github.com/uqfoundation/dill/releases/download/dill-%s/dill-%s.tar.gz',
      python_requires='>=2.7, !=3.0.*',
      classifiers = ['Development Status :: 5 - Production/Stable',
                     'Intended Audience :: Developers',
                     'Intended Audience :: Science/Research',
                     'License :: OSI Approved :: BSD License',
                     'Programming Language :: Python :: 2',
                     'Programming Language :: Python :: 2.7',
                     'Programming Language :: Python :: 3',
                     'Programming Language :: Python :: 3.6',
                     'Programming Language :: Python :: 3.7',
                     'Programming Language :: Python :: 3.8',
                     'Programming Language :: Python :: 3.9',
                     'Topic :: Scientific/Engineering',
                     'Topic :: Software Development'],

      packages = ['dill','dill.tests'],
      package_dir = {'dill':'dill', 'dill.tests':'tests'},
""" % (target_version, long_description, stable_version, stable_version)

# add dependencies
ctypes_version = '>=1.0.1'
objgraph_version = '>=1.7.2'
pyreadline_version = '>=1.7.1'
if has_setuptools:
    setup_code += """
      zip_safe=False,
"""
    if sys.platform[:3] == 'win':
        setup_code += """
      extras_require = {'readline': ['pyreadline%s'], 'graph': ['objgraph%s']},
""" % (pyreadline_version, objgraph_version)
    # verrrry unlikely that this is still relevant
    elif hex(sys.hexversion) < '0x20500f0':
        setup_code += """
      install_requires = ['ctypes%s'],
      extras_require = {'readline': [], 'graph': ['objgraph%s']},
""" % (ctypes_version, objgraph_version)
    else:
        setup_code += """
      extras_require = {'readline': [], 'graph': ['objgraph%s']},
""" % (objgraph_version)

# add the scripts, and close 'setup' call
setup_code += """    
      scripts=['scripts/undill','scripts/get_objgraph'])
"""

# exec the 'setup' code
exec(setup_code)

# if dependencies are missing, print a warning
try:
    import ctypes
    import readline
except ImportError:
    print ("\n***********************************************************")
    print ("WARNING: One of the following dependencies is unresolved:")
    print ("    ctypes %s" % ctypes_version)
    if sys.platform[:3] == 'win':
        print ("    readline %s" % pyreadline_version)
    print ("***********************************************************\n")


if __name__=='__main__':
    pass

# end of file
