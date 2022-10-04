#!/usr/bin/env python
#
# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
Auxiliary classes and functions used in more than one module, defined here to
avoid circular import problems.
"""

import contextlib
import io
import math
from contextlib import suppress

#NOTE: dill._dill is not completely loaded at this point, can't import from it.
from dill import _dill

# Type hints.
from typing import Tuple, Union

def _format_bytes_size(size: Union[int, float]) -> Tuple[int, str]:
    """Return bytes size text representation in human-redable form."""
    unit = "B"
    power_of_2 = math.trunc(size).bit_length() - 1
    magnitude = min(power_of_2 - power_of_2 % 10, 80)  # 2**80 == 1 YiB
    if magnitude:
        # Rounding trick: 1535 (1024 + 511) -> 1K; 1536 -> 2K
        size = ((size >> magnitude-1) + 1) >> 1
        unit = "%siB" % "KMGTPEZY"[(magnitude // 10) - 1]
    return size, unit


## File-related utilities ##

class _PeekableReader(contextlib.AbstractContextManager):
    """lightweight readable stream wrapper that implements peek()"""
    def __init__(self, stream, closing=True):
        self.stream = stream
        self.closing = closing
    def __exit__(self, *exc_info):
        if self.closing:
            self.stream.close()
    def read(self, n):
        return self.stream.read(n)
    def readline(self):
        return self.stream.readline()
    def tell(self):
        return self.stream.tell()
    def close(self):
        return self.stream.close()
    def peek(self, n):
        stream = self.stream
        try:
            if hasattr(stream, 'flush'):
                stream.flush()
            position = stream.tell()
            stream.seek(position)  # assert seek() works before reading
            chunk = stream.read(n)
            stream.seek(position)
            return chunk
        except (AttributeError, OSError):
            raise NotImplementedError("stream is not peekable: %r", stream) from None

class _SeekableWriter(io.BytesIO, contextlib.AbstractContextManager):
    """works as an unlimited buffer, writes to file on close"""
    def __init__(self, stream, closing=True, *args, **kwds):
        super().__init__(*args, **kwds)
        self.stream = stream
        self.closing = closing
    def __exit__(self, *exc_info):
        self.close()
    def close(self):
        self.stream.write(self.getvalue())
        with suppress(AttributeError):
            self.stream.flush()
        super().close()
        if self.closing:
            self.stream.close()

def _open(file, mode, *, peekable=False, seekable=False):
    """return a context manager with an opened file-like object"""
    readonly = ('r' in mode and '+' not in mode)
    if not readonly and peekable:
        raise ValueError("the 'peekable' option is invalid for writable files")
    if readonly and seekable:
        raise ValueError("the 'seekable' option is invalid for read-only files")
    should_close = not hasattr(file, 'read' if readonly else 'write')
    if should_close:
        file = open(file, mode)
    # Wrap stream in a helper class if necessary.
    if peekable and not hasattr(file, 'peek'):
        # Try our best to return it as an object with a peek() method.
        if hasattr(file, 'seekable'):
            file_seekable = file.seekable()
        elif hasattr(file, 'seek') and hasattr(file, 'tell'):
            try:
                file.seek(file.tell())
                file_seekable = True
            except Exception:
                file_seekable = False
        else:
            file_seekable = False
        if file_seekable:
            file = _PeekableReader(file, closing=should_close)
        else:
            try:
                file = io.BufferedReader(file)
            except Exception:
                # It won't be peekable, but will fail gracefully in _identify_module().
                file = _PeekableReader(file, closing=should_close)
    elif seekable and (
        not hasattr(file, 'seek')
        or not hasattr(file, 'truncate')
        or (hasattr(file, 'seekable') and not file.seekable())
    ):
        file = _SeekableWriter(file, closing=should_close)
    if should_close or isinstance(file, (_PeekableReader, _SeekableWriter)):
        return file
    else:
        return contextlib.nullcontext(file)
