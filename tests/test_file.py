#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill
import random
import os

fname = "_test_file.txt"
rand_chars = list(map(chr, range(32, 255))) + ["\n"] * 40  # bias newline


def write_randomness(number=200):
    with open(fname, "w") as f:
        for i in range(number):
            f.write(random.choice(rand_chars))
    with open(fname, "r") as f:
        contents = f.read()
    return contents


def throws(op, args, exc):
    try:
        op(*args)
    except exc:
        return True
    else:
        return False


def test(safefmode=False, kwargs={}):
    # file exists, with same contents
    # read

    write_randomness()

    f = open(fname, "r")
    _f = dill.loads(dill.dumps(f, **kwargs))
    assert _f.mode == f.mode
    assert _f.tell() == f.tell()
    assert _f.read() == f.read()
    f.close()
    _f.close()

    # write

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, **kwargs)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    f2 = dill.loads(f_dumped)
    f2mode = f2.mode
    f2tell = f2.tell()
    f2.write(" world!")
    f2.close()
 
    # 1) preserve mode and position  #FIXME
    assert open(fname).read() == "\x00\x00\x00\x00\x00 world!"
    assert f2mode == fmode
    assert f2tell == ftell
    # 2) treat as if new filehandle, will truncate file
    # assert open(fname).read() == " world!"
    # assert f2mode == fmode
    # assert f2tell == 0
    # 3) prefer data over filehandle state
    # assert open(fname).read() == "hello world!"
    # assert f2mode == 'r+'  #XXX: have to decide 'r+', 'a', ...?
    # assert f2tell == ftell
    # 4) use "r" to read data, then use "w" to write new file
    # assert open(fname).read() == "hello world!"
    # assert f2mode == fmode
    # assert f2tell == ftell
    # 5) pickle data along with filehandle  #XXX: Yikes
    # assert open(fname).read() == "hello world!"
    # assert f2mode == fmode
    # assert f2tell == ftell

    # file exists, with different contents (smaller size)
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, **kwargs)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    _flen = 150
    _fstr = write_randomness(number=_flen)

    if safefmode: # throw error if ftell > EOF
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        assert f2.mode == fmode
        # 1) preserve mode and position  #XXX: ?
        assert f2.tell() == ftell # 200
        assert f2.read() == ""
        f2.seek(0)
        assert f2.read() == _fstr
        assert f2.tell() == _flen # 150
        # 3) prefer data over filehandle state
        # assert f2.tell() == ftell # 200
        # assert f2.read() == ""
        # f2.seek(0)
        # assert f2.read() == _fstr
        # assert f2.tell() == _flen # 150
        # 4) preserve mode and position, seek(EOF) if ftell > EOF
        # assert f2.tell() == _flen # 150
        # assert f2.read() == ""
        # f2.seek(0)
        # assert f2.read() == _fstr
        # assert f2.tell() == _flen # 150
        # 2) treat as if new filehandle, will seek(0)
        # assert f2.tell() == 0
        # assert f2.read() == _fstr
        # assert f2.tell() == _flen # 150
        # 5) pickle data along with filehandle  #XXX: Yikes
        # assert f2.tell() == ftell # 200
        # assert f2.read() == ""
        # f2.seek(0)
        # assert f2.read() == fstr
        # assert f2.tell() == ftell # 200
        f2.close()

    # write

    write_randomness()

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, **kwargs)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    fstr = open(fname).read()

    f = open(fname, "w")
    f.write("h")
    _ftell = f.tell()
    f.close()

    if safefmode: # throw error if ftell > EOF
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        # 1) preserve mode and position  #FIXME
        assert open(fname).read() == "\x00\x00\x00\x00\x00 world!"
        assert f2mode == fmode
        assert f2tell == ftell
        # 3) prefer data over filehandle state
        # assert open(fname).read() == "h\x00\x00\x00\x00 world!"
        # assert f2mode == 'r+'  #XXX: have to decide 'r+', 'a', ...?
        # assert f2tell == ftell
        # 2) treat as if new filehandle, will truncate file
        # assert open(fname).read() == " world!"
        # assert f2mode == fmode
        # assert f2tell == 0
        # 5) pickle data along with filehandle  #XXX: Yikes
        # assert open(fname).read() == "hello world!"
        # assert f2mode == fmode
        # assert f2tell == ftell
        # 4a) use "r" to read data, then use "w" to write new file
        # assert open(fname).read() == "h\x00\x00\x00\x00 world!"
        # assert f2mode == fmode
        # assert f2tell == ftell
        # 4b) preserve mode and position, seek(EOF) if ftell > EOF
        # assert open(fname).read() == "h world!"
        # assert f2mode == fmode
        # assert f2tell == _ftell
        f2.close()

    # file does not exist
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, **kwargs)
    fmode = f.mode
    ftell = f.tell()
    f.close()

    os.remove(fname)

    if safefmode: # throw error if file DNE
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        assert f2.mode == fmode
        # 1) preserve mode and position  #XXX: ?
        assert f2.tell() == ftell # 200
        assert f2.read() == ""
        f2.seek(0)
        assert f2.read() == ""
        assert f2.tell() == 0
        # 3) prefer data over filehandle state
        # assert f2.tell() == ftell # 200
        # assert f2.read() == ""
        # f2.seek(0)
        # assert f2.read() == ""
        # assert f2.tell() == 0
        # 5) pickle data along with filehandle  #XXX: Yikes
        # assert f2.tell() == ftell # 200
        # assert f2.read() == ""
        # f2.seek(0)
        # assert f2.read() == fstr
        # assert f2.tell() == ftell # 200
        # 2) treat as if new filehandle, will seek(0)
        # assert f2.tell() == 0
        # assert f2.read() == ""
        # assert f2.tell() == 0
        # 4) preserve mode and position, seek(EOF) if ftell > EOF
        # assert f2.tell() == 0
        # assert f2.read() == ""
        # f2.seek(0)
        # assert f2.read() == ""
        # assert f2.tell() == 0
        f2.close()

    # write

    write_randomness()

    f = open(fname, "w+")
    f.write("hello")
    f_dumped = dill.dumps(f, **kwargs)
    ftell = f.tell()
    fmode = f.mode
    f.close()

    os.remove(fname)

    if safefmode: # throw error if file DNE
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        # 1) preserve mode and position  #FIXME
        assert open(fname).read() == "\x00\x00\x00\x00\x00 world!"
        assert f2mode == fmode
        assert f2tell == ftell
        # 3) prefer data over filehandle state
        # assert open(fname).read() == "\x00\x00\x00\x00\x00 world!"
        # assert f2mode == 'r+'  #XXX: have to decide 'r+', 'a', ...?
        # assert f2tell == ftell
        # 2) treat as if new filehandle, will truncate file
        # assert open(fname).read() == " world!"
        # assert f2mode == fmode
        # assert f2tell == 0
        # 5) pickle data along with filehandle  #XXX: Yikes
        # assert open(fname).read() == "hello world!"
        # assert f2mode == fmode
        # assert f2tell == ftell
        # 4a) use "r" to read data, then use "w" to write new file
        # assert open(fname).read() == "\x00\x00\x00\x00\x00 world!"
        # assert f2mode == fmode
        # assert f2tell == ftell
        # 4b) preserve mode and position, seek(EOF) if ftell > EOF
        # assert open(fname).read() == " world!"
        # assert f2mode == fmode
        # assert f2tell == 0

    # file exists, with different contents (larger size)
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, **kwargs)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    _flen = 250
    _fstr = write_randomness(number=_flen)

    #XXX: no safefmode: no way to be 'safe'?

    f2 = dill.loads(f_dumped)
    assert f2.mode == fmode
    # 1) preserve mode and position  #XXX: ?
    assert f2.tell() == ftell # 200
    assert f2.read() == _fstr[ftell:]
    f2.seek(0)
    assert f2.read() == _fstr
    assert f2.tell() == _flen # 250
    # 3) prefer data over filehandle state
    # assert f2.tell() == ftell # 200
    # assert f2.read() == _fstr[ftell:]
    # f2.seek(0)
    # assert f2.read() == _fstr
    # assert f2.tell() == _flen # 250
    # 4) preserve mode and position, seek(EOF) if ftell > EOF
    # assert f2.tell() == ftell # 200
    # assert f2.read() == _fstr[ftell:]
    # f2.seek(0)
    # assert f2.read() == _fstr
    # assert f2.tell() == _flen # 250
    # 2) treat as if new filehandle, will seek(0)
    # assert f2.tell() == 0
    # assert f2.read() == _fstr
    # assert f2.tell() == _flen # 250
    # 5) pickle data along with filehandle  #XXX: Yikes
    # assert f2.tell() == ftell # 200
    # assert f2.read() == ""
    # f2.seek(0)
    # assert f2.read() == fstr
    # assert f2.tell() == ftell # 200
    f2.close()  #XXX: other alternatives?

    # write

    write_randomness()

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, **kwargs)
    fmode = f.mode
    ftell = f.tell()
#   f.close()
    fstr = open(fname).read()

#   f = open(fname, "a")
    f.write(" and goodbye!")
    _ftell = f.tell()
    f.close()

    #XXX: no safefmode: no way to be 'safe'?

    f2 = dill.loads(f_dumped)
    f2mode = f2.mode
    f2tell = f2.tell()
    f2.write(" world!")
    f2.close()
    # 1) preserve mode and position  #FIXME
    assert open(fname).read() == "\x00\x00\x00\x00\x00 world!"
    assert f2mode == fmode
    assert f2tell == ftell
    # 3) prefer data over filehandle state
    # assert open(fname).read() == "hello world!odbye!"
    # assert f2mode == 'r+'  #XXX: have to decide 'r+', 'a', ...?
    # assert f2tell == ftell
    # 2) treat as if new filehandle, will truncate file
    # assert open(fname).read() == " world!"
    # assert f2mode == fmode
    # assert f2tell == 0
    # 5) pickle data along with filehandle  #XXX: Yikes
    # assert open(fname).read() == "hello world!"
    # assert f2mode == fmode
    # assert f2tell == ftell
    # 4) use "r" to read data, then use "w" to write new file
    # assert open(fname).read() == "hello world!odbye!"
    # assert f2mode == fmode
    # assert f2tell == ftell
    f2.close()

    # TODO:
    # <for all above cases>
    # append


test()
# TODO: switch this on when #57 is closed
# test(True, {"safe_file": True})
if os.path.exists(fname):
    os.remove(fname)
