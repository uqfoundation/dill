#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from __future__ import absolute_import

from os import path
from setuptools import setup, find_packages
from distutils.file_util import copy_file

_here = path.abspath(path.dirname(__file__))

copy_file(path.join(_here, 'README.rst'), path.join(_here, 'dill'))
copy_file(path.join(_here, 'LICENSE'), path.join(_here, 'dill'))

with open(path.join(_here, 'README.rst')) as f:
    long_description = f.read()

# build the 'setup' call
setup(
    name='dill',
    use_scm_version={
        'version_scheme': 'guess-next-dev',
        'local_scheme': 'dirty-tag',
        'write_to': 'dill/_version.py'
    },
    description='serialize all of python',
    long_description = long_description,
    author_email = 'mmckerns at uqfoundation dot org',
    maintainer = 'Mike McKerns',
    maintainer_email = 'mmckerns at uqfoundation dot org',
    license = '3-clause BSD',
    url = 'http://trac.mystic.cacr.caltech.edu/project/pathos/wiki/dill.html',
    classifiers = (
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development'
    ),

    packages=find_packages(),
    include_package_data=True,
    package_data={'': ['LICENSE', '*.rst']},
    zip_safe=False,
    install_requires=[],
    setup_requires=['setuptools-scm>=1.6.0'],
    extras_require={
        'optional': [
            'objgraph>=1.7.2', 
            'numpy>=1.6'
        ],
        ":sys_platform=='win32'": "pyreadline>=1.7.1",
    },
    entry_points={
        'console_scripts': [
            'get_objgraph = dill.get_objgraph:main',
            'unpickle = dill.unpickle:main',
        ],
    },
)
