#!/usr/bin/env python
#
# Michael McKerns
# mmckerns@caltech.edu

# check if easy_install is available
try:
#   import __force_distutils__ #XXX: uncomment to force use of distutills
    from setuptools import setup
    has_setuptools = True
except ImportError:
    from distutils.core import setup
    has_setuptools = False

# build the 'setup' call
setup_code = """
setup(name='dill',
      version='0.1a1',
      description='a full python state pickler',
      author = 'Mike McKerns',
      maintainer = 'Mike McKerns',
      maintainer_email = 'mmckerns@caltech.edu',
      license = 'BSD',
      platforms = ['any'],
      url = 'http://www.cacr.caltech.edu/~mmckerns',
      classifiers = ('Intended Audience :: Developers',
                     'Programming Language :: Python',
                     'Topic :: Physics Programming'),

      packages = ['dill'],
      package_dir = {'dill':'dill'},
"""

# add dependencies
#

# close 'setup' call
setup_code += """    
      zip_safe=True,
      scripts=[])
"""

# exec the 'setup' code
exec setup_code

# if dependencies are missing, print a warning
# 

if __name__=='__main__':
    pass

# end of file
