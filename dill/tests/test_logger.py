#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import contextlib
import logging
import re
from os.path import join
import tempfile

import dill
from dill import detect
from dill.logger import stderr_handler, adapter as logger

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

test_obj = {'a': (1, 2), 'b': object(), 'f': lambda x: x**2, 'big': list(range(10))}

def test_logging(should_trace):
    buffer = StringIO()
    handler = logging.StreamHandler(buffer)
    logger.addHandler(handler)
    try:
        dill.dumps(test_obj)
        if should_trace:
            regex = re.compile(r'(\S*┬ \w.*[^)]'              # begin pickling object
                               r'|│*└ # \w.* \[\d+ (\wi)?B])' # object written (with size)
                               )
            for line in buffer.getvalue().splitlines():
                assert regex.fullmatch(line)
            return buffer.getvalue()
        else:
            assert buffer.getvalue() == ""
    finally:
        logger.removeHandler(handler)
        buffer.close()

def test_trace_to_file(stream_trace):
    file = tempfile.NamedTemporaryFile(mode='r')
    with detect.trace(file.name, mode='w'):
        dill.dumps(test_obj)
    file_trace = file.read()
    file.close()
    # Apparently, objects can change location in memory...
    reghex = re.compile(r'0x[0-9A-Za-z]+')
    file_trace, stream_trace = reghex.sub('0x', file_trace), reghex.sub('0x', stream_trace)
    # PyPy prints dictionary contents with repr(dict)...
    regdict = re.compile(r'(dict\.__repr__ of ).*')
    file_trace, stream_trace = regdict.sub(r'\1{}>', file_trace), regdict.sub(r'\1{}>', stream_trace)
    assert file_trace == stream_trace

def test_trace_file_permissions():
    # a trace redirected to a new file must not be group/other accessible;
    # it can contain object reprs and whatever log() writes
    import os, platform
    if os.name != 'posix' or platform.python_implementation() == 'PyPy':
        return
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'trace.log')
    old_umask = os.umask(0o022)  # a permissive umask exposes a missing mode
    try:
        with detect.trace(path) as log:
            log("secret = %r", {'token': 's3cr3t'})
            dill.dumps(test_obj)
        bits = os.stat(path).st_mode & 0o777
        assert bits & 0o077 == 0, "trace file is group/other accessible: %o" % bits
    finally:
        os.umask(old_umask)
        if os.path.exists(path):
            os.remove(path)
        os.rmdir(d)

def test_nested_trace_redirects():
    for raise_error in (False, True):
        with StringIO() as outer, StringIO() as inner, StringIO() as errors:
            old_level = logger.getEffectiveLevel()
            with contextlib.redirect_stderr(errors):
                with detect.trace(outer) as log:
                    log('outer-before')
                    try:
                        with detect.trace(inner) as inner_log:
                            inner_log('inner-only')
                            if raise_error:
                                raise RuntimeError('leave inner trace')
                    except RuntimeError:
                        pass
                    log('outer-after')
            assert outer.getvalue() == 'outer-before\nouter-after\n'
            assert inner.getvalue() == 'inner-only\n'
            assert errors.getvalue() == ''
            assert logger.getEffectiveLevel() == old_level


def test_trace_redirect_exit_order():
    with tempfile.TemporaryDirectory() as directory, StringIO() as errors:
        first_path = join(directory, 'first.log')
        second_path = join(directory, 'second.log')
        first = detect.trace(first_path)
        second = detect.trace(second_path)
        old_level = logger.getEffectiveLevel()
        try:
            with contextlib.redirect_stderr(errors):
                first.__enter__()('first-only')
                second.__enter__()('second-only')
                first.__exit__()
                second.__exit__()
                with detect.trace() as log:
                    log('after-redirects')
        finally:
            logger.setLevel(old_level)
        assert errors.getvalue() == 'after-redirects\n'
        with open(first_path) as f:
            assert f.read() == 'first-only\n'
        with open(second_path) as f:
            assert f.read() == 'second-only\n'


if __name__ == '__main__':
    logger.removeHandler(stderr_handler)
    test_logging(should_trace=False)
    detect.trace(True)
    test_logging(should_trace=True)
    detect.trace(False)
    test_logging(should_trace=False)

    loglevel = logging.ERROR
    logger.setLevel(loglevel)
    with detect.trace():
        stream_trace = test_logging(should_trace=True)
    test_logging(should_trace=False)
    assert logger.getEffectiveLevel() == loglevel
    test_trace_to_file(stream_trace)
    test_trace_file_permissions()
    test_nested_trace_redirects()
    test_trace_redirect_exit_order()
