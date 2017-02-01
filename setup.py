#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2017 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from __future__ import with_statement, absolute_import
import os

# set version numbers
stable_version = '0.2.6'
target_version = '0.2.6'
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

`dill` extends python's `pickle` module for serializing and de-serializing
python objects to the majority of the built-in python types. Serialization
is the process of converting an object to a byte stream, and the inverse
of which is converting a byte stream back to on python object hierarchy.

`dill` provides the user the same interface as the `pickle` module, and
also includes some additional features. In addition to pickling python
objects, `dill` provides the ability to save the state of an interpreter
session in a single command.  Hence, it would be feasable to save a
interpreter session, close the interpreter, ship the pickled file to
another computer, open a new interpreter, unpickle the session and
thus continue from the 'saved' state of the original interpreter
session.

`dill` can be used to store python objects to a file, but the primary
usage is to send python objects across the network as a byte stream.
`dill` is quite flexible, and allows arbitrary user defined classes
and funcitons to be serialized.  Thus `dill` is not intended to be
secure against erroneously or maliciously constructed data. It is
left to the user to decide whether the data they unpickle is from
a trustworthy source.

`dill` is part of `pathos`, a python framework for heterogeneous computing.
`dill` is in active development, so any user feedback, bug reports, comments,
or suggestions are highly appreciated.  A list of known issues is maintained
at http://trac.mystic.cacr.caltech.edu/project/pathos/query, with a public
ticket list at https://github.com/uqfoundation/dill/issues.


Major Features
==============

`dill` can pickle the following standard types::

    - none, type, bool, int, long, float, complex, str, unicode,
    - tuple, list, dict, file, buffer, builtin,
    - both old and new style classes,
    - instances of old and new style classes,
    - set, frozenset, array, functions, exceptions

`dill` can also pickle more 'exotic' standard types::

    - functions with yields, nested functions, lambdas,
    - cell, method, unboundmethod, module, code, methodwrapper,
    - dictproxy, methoddescriptor, getsetdescriptor, memberdescriptor,
    - wrapperdescriptor, xrange, slice,
    - notimplemented, ellipsis, quit

`dill` cannot yet pickle these standard types::

    - frame, generator, traceback

`dill` also provides the capability to::

    - save and load python interpreter sessions
    - save and extract the source code from functions and classes
    - interactively diagnose pickling errors


Current Release
===============

This version is `dill-%(relver)s`.

The latest released version of `dill` is available from::

    http://trac.mystic.cacr.caltech.edu/project/pathos

or::

    https://github.com/uqfoundation/dill/releases

or also::

    https://pypi.python.org/pypi/dill

`dill` is distributed under a 3-clause BSD license.

    >>> import dill
    >>> print (dill.license())


Development Version 
===================

You can get the latest development version with all the shiny new features at::

    https://github.com/uqfoundation

If you have a new contribution, please submit a pull request.


Installation
============

`dill` is packaged to install from source, so you must
download the tarball, unzip, and run the installer::

    [download]
    $ tar -xvzf dill-%(thisver)s.tgz
    $ cd dill-%(thisver)s
    $ python setup py build
    $ python setup py install

You will be warned of any missing dependencies and/or settings
after you run the "build" step above. 

Alternately, `dill` can be installed with `pip` or `easy_install`::

    $ pip install dill


Requirements
============

`dill` requires::

    - python2, version >= 2.5  *or*  python3, version >= 3.1  *or*  pypy
    - pyreadline, version >= 1.7.1  (on windows)

Optional requirements::

    - setuptools, version >= 0.6
    - objgraph, version >= 1.7.2


More Information
================

Probably the best way to get started is to look at the tests that are
provided within `dill`. See `dill.tests` for a set of scripts that demonstrate
how `dill` can serialize different python objects.  Since `dill` conforms
to the `pickle` interface, the examples and documentation at
http://docs.python.org/library/pickle.html also apply to `dill` if one will
`import dill as pickle`. The source code is also generally well
documented, so further questions may be resolved by inspecting the code
itself.  Please also feel free to submit a ticket on github, or ask a
question on stackoverflow (@Mike McKerns).

`dill` is an active research tool. There are a growing number of publications
and presentations that discuss real-world examples and new features of `dill`
in greater detail than presented in the user's guide.  If you would like to
share how you use `dill` in your work, please post a link or send an email
(to mmckerns at uqfoundation dot org).


Citation
========

If you use `dill` to do research that leads to publication, we ask that you
acknowledge use of `dill` by citing the following in your publication::

    M.M. McKerns, L. Strand, T. Sullivan, A. Fang, M.A.G. Aivazis,
    "Building a framework for predictive science", Proceedings of
    the 10th Python in Science Conference, 2011;
    http://arxiv.org/pdf/1202.1056

    Michael McKerns and Michael Aivazis,
    "pathos: a framework for heterogeneous computing", 2010- ;
    http://trac.mystic.cacr.caltech.edu/project/pathos

Please see http://trac.mystic.cacr.caltech.edu/project/pathos or
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
      author_email = 'mmckerns at uqfoundation dot org',
      maintainer = 'Mike McKerns',
      maintainer_email = 'mmckerns at uqfoundation dot org',
      license = '3-clause BSD',
      platforms = ['Linux', 'Windows', 'Mac'],
      url = 'http://www.cacr.caltech.edu/~mmckerns/dill.htm',
      download_url = 'http://dev.danse.us/packages',
      classifiers = ('Development Status :: 5 - Production/Stable',
                     'Intended Audience :: Developers',
                     'Intended Audience :: Science/Research',
                     'License :: OSI Approved :: BSD License',
                     'Programming Language :: Python :: 2',
                     'Programming Language :: Python :: 3',
                     'Topic :: Scientific/Engineering',
                     'Topic :: Software Development'),

      packages = ['dill'],
      package_dir = {'dill':'dill'},
""" % (target_version, long_description)

# add dependencies
ctypes_version = '>=1.0.1'
objgraph_version = '>=1.7.2'
pyreadline_version = '>=1.7.1'
import sys
if has_setuptools:
    setup_code += """
      zip_safe=False,
"""
    if sys.platform[:3] == 'win':
        setup_code += """
      install_requires = ['pyreadline%s'],
""" % (pyreadline_version)
    # verrrry unlikely that this is still relevant
    elif hex(sys.hexversion) < '0x20500f0':
        setup_code += """
      install_requires = ['ctypes%s'],
""" % (ctypes_version)

# add the scripts, and close 'setup' call
setup_code += """    
      scripts=['scripts/dill_unpickle.py','scripts/get_objgraph.py'])
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
