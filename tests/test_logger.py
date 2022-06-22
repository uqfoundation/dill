#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import dill, logging, re
from dill.logger import handler, adapter as logger

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

def test_logging(regex=None):
    buffer = StringIO()
    handler = logging.StreamHandler(buffer)
    logger.addHandler(handler)
    try:
        dill.dumps({'a': (1, 2), 'b': object(), 'big': list(range(10000))})
        if regex is None:
            assert buffer.getvalue() == ""
        else:
            regex = re.compile(regex)
            for line in buffer.getvalue().splitlines():
                assert regex.fullmatch(line)
    finally:
        logger.removeHandler(handler)
        buffer.close()

if __name__ == '__main__':
    logger.removeHandler(handler)
    test_logging()
    dill.detect.trace(True)
    test_logging(r'(\S*┬ \w.*[^)]'              # begin pickling object
                 r'|│*└ # \w.* \[\d+ (\wi)?B])' # object written (with size)
                 )
    dill.detect.trace(False)
    test_logging()
