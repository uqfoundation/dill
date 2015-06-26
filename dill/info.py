# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

from os import path

_here = path.abspath(path.dirname(__file__))

with open(path.join(_here, 'README.rst')) as f:
    readme = f.read()

with open(path.join(_here, 'LICENSE')) as f:
    license = f.read()
