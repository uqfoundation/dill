#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill
import random
import os

fname = "test_file.txt"
rand_chars = list(map(chr, range(32, 255))) + ["\n"] * 40  # bias newline


def write_randomness(number=200):
    with open(fname, "w") as f:
        for i in range(number):
            f.write(random.choice(rand_chars))


def throws(op, args, exc):
    try:
        op(*args)
    except exc:
        return True
    else:
        return False


def test(testsafefmode=False, kwargs={}):
    # file exists, with same contents
    # read

    write_randomness()

    f = open(fname, "r")
    assert dill.loads(dill.dumps(f, **kwargs)).read() == f.read()
    f.close()

    # write

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, **kwargs)
    f.close()
    f2 = dill.loads(f_dumped)
    f2.write(" world!")
    f2.close()

    assert open(fname).read() == "hello world!"

    # file exists, with different contents (smaller size)
    # read

    write_randomness()

    f = open(fname, "r")
    f.read()
    f_dumped = dill.dumps(f, **kwargs)
    f.close()
    write_randomness(number=150)

    if testsafefmode:
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        assert f2.read() == ""
        f2.close()

    # write

    write_randomness()

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, **kwargs)
    f.close()

    f = open(fname, "w")
    f.write("h")
    f.close()

    if testsafefmode:
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        f2.write(" world!")
        f2.close()
        assert open(fname).read() == "h\x00\x00\x00\x00 world!"

    # file does not exist
    # read

    write_randomness()

    f = open(fname, "r")
    f.read()
    f_dumped = dill.dumps(f, **kwargs)
    f.close()

    os.remove(fname)

    if testsafefmode:
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        assert f2.read() == ""
        f2.close()

    # write

    write_randomness()

    f = open(fname, "w+")
    f.write("hello")
    f_dumped = dill.dumps(f, **kwargs)
    f.close()

    os.remove(fname)

    if testsafefmode:
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        f2.write(" world!")
        f2.close()
        assert open(fname).read() == "\x00\x00\x00\x00\x00 world!"

test()
# TODO: switch this on when #57 is closed
# test(True, {"safe_file": True})
if os.path.exists(fname):
    os.remove(fname)
