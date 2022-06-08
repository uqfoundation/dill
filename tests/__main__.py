#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2018-2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from __future__ import print_function
import argparse, glob, logging, os
try:
    import pox
    python = pox.which_python(version=True, fullpath=False) or 'python'
except ImportError:
    python = 'python'
import subprocess as sp
from sys import platform

parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', help="increase verbosity", action='store_true')
if parser.parse_args().verbose:
    logging.basicConfig(level=logging.INFO)

shell = platform[:3] == 'win'

suite = os.path.dirname(__file__) or os.path.curdir
tests = glob.glob(suite + os.path.sep + 'test_*.py')


if __name__ == '__main__':

    os.environ['CI'] = 'true'
    for test in tests:
        logging.info(" %s\n", test)
        p = sp.Popen([python, test], shell=shell).wait()
        if not p:
            print('.', end='', flush=True)
    print('')
