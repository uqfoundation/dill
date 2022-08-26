#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

"""test general utilities in _utils.py (for filters, see test_filtering.py)"""

import io
import os
import sys

from dill import _utils

def test_open():
    file_unpeekable = open(__file__, 'rb', buffering=0)
    assert not hasattr(file_unpeekable, 'peek')

    content = file_unpeekable.read()
    peeked_chars = content[:10]
    first_line = content[:100].partition(b'\n')[0] + b'\n'
    file_unpeekable.seek(0)

    # Test _PeekableReader for seekable stream
    with _utils._open(file_unpeekable, 'r', peekable=True) as file:
        assert file.peek(10)[:10] == peeked_chars
        assert file.readline() == first_line
        assert isinstance(file, _utils._PeekableReader)
    assert not file_unpeekable.closed
    file_unpeekable.close()

    _pipe_r, _pipe_w = os.pipe()
    pipe_r, pipe_w = io.FileIO(_pipe_r, closefd=False), io.FileIO(_pipe_w, mode='w')
    assert not hasattr(pipe_r, 'peek')
    assert not pipe_r.seekable()
    assert not pipe_w.seekable()

    # Test io.BufferedReader for unseekable stream
    with _utils._open(pipe_r, 'r', peekable=True) as file:
        pipe_w.write(content[:100])
        assert file.peek(10)[:10] == peeked_chars
        assert file.readline() == first_line
        assert isinstance(file, io.BufferedReader)
    assert not pipe_r.closed

    # Test _Seekable writer for unseekable stream
    with _utils._open(pipe_w, 'w', seekable=True) as file:
        # pipe_r is closed here for some reason...
        file.write(content)
        file.flush()
        file.seek(0)
        file.truncate()
        file.write(b'a line of text\n')
    assert not pipe_w.closed
    pipe_r = io.FileIO(_pipe_r)
    assert pipe_r.readline()  == b'a line of text\n'
    pipe_r.close()
    pipe_w.close()

if __name__ == '__main__':
    test_open()
