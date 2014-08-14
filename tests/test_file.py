# usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2014 California Institute of Technology.
# License: 3-clause BSD.  The full license text is available at:
#  - http://trac.mystic.cacr.caltech.edu/project/pathos/browser/dill/LICENSE

import dill
import random
import os
import string

fname = "_test_file.txt"
rand_chars = list(string.ascii_letters) + ["\n"] * 40  # bias newline


def write_randomness(number=200):
    with open(fname, "w") as f:
        for i in range(number):
            f.write(random.choice(rand_chars))
    with open(fname, "r") as f:
        contents = f.read()
    return contents


def trunc_file():
    open(fname, "w").close()


def throws(op, args, exc):
    try:
        op(*args)
    except exc:
        return True
    else:
        return False


def test(safe_file, file_mode):
    # file exists, with same contents
    # read

    write_randomness()

    f = open(fname, "r")
    _f = dill.loads(dill.dumps(f, safe_file=safe_file, file_mode=file_mode))
    assert _f.mode == f.mode
    assert _f.tell() == f.tell()
    assert _f.read() == f.read()
    f.close()
    _f.close()

    # write

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    f2 = dill.loads(f_dumped)
    f2mode = f2.mode
    f2tell = f2.tell()
    f2.write(" world!")
    f2.close()

    if file_mode == dill.FMODE_NEWHANDLE:
        assert open(fname).read() == " world!"
        assert f2mode == fmode
        assert f2tell == 0
    elif file_mode == dill.FMODE_PRESERVEDATA:
        assert open(fname).read() == "hello world!"
        assert f2mode == 'r+'
        assert f2tell == ftell
    elif file_mode == dill.FMODE_PICKLECONTENTS:
        assert open(fname).read() == "hello world!"
        assert f2mode == fmode
        assert f2tell == ftell
    else:
        raise RuntimeError("Uncovered file mode!")

    # append

    trunc_file()

    f = open(fname, "a")
    f.write("hello")
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    f2 = dill.loads(f_dumped)
    f2mode = f2.mode
    f2tell = f2.tell()
    f2.write(" world!")
    f2.close()

    assert f2mode == fmode
    if file_mode == dill.FMODE_PRESERVEDATA:
        assert open(fname).read() == "hello world!"
        assert f2tell == ftell
    elif file_mode == dill.FMODE_NEWHANDLE:
        assert open(fname).read() == "hello world!"
        assert f2tell == ftell
    elif file_mode == dill.FMODE_PICKLECONTENTS:
        assert open(fname).read() == "hello world!"
        assert f2tell == ftell
    else:
        raise RuntimeError("Uncovered file mode!")

    # file exists, with different contents (smaller size)
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    _flen = 150
    _fstr = write_randomness(number=_flen)

    if safe_file:  # throw error if ftell > EOF
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        assert f2.mode == fmode
        if file_mode == dill.FMODE_PRESERVEDATA:
            assert f2.tell() == _flen
            assert f2.read() == ""
            f2.seek(0)
            assert f2.read() == _fstr
            assert f2.tell() == _flen  # 150
        elif file_mode == dill.FMODE_NEWHANDLE:
            assert f2.tell() == 0
            assert f2.read() == _fstr
            assert f2.tell() == _flen  # 150
        elif file_mode == dill.FMODE_PICKLECONTENTS:
            assert f2.tell() == ftell  # 200
            assert f2.read() == ""
            f2.seek(0)
            assert f2.read() == fstr
            assert f2.tell() == ftell  # 200
        else:
            raise RuntimeError("Uncovered file mode!")
        f2.close()

    # write

    write_randomness()

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    fstr = open(fname).read()

    f = open(fname, "w")
    f.write("h")
    _ftell = f.tell()
    f.close()

    if safe_file:  # throw error if ftell > EOF
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        if file_mode == dill.FMODE_PRESERVEDATA:
            assert open(fname).read() == "h world!"
            assert f2mode == 'r+'
            assert f2tell == _ftell
        elif file_mode == dill.FMODE_NEWHANDLE:
            assert open(fname).read() == " world!"
            assert f2mode == fmode
            assert f2tell == 0
        elif file_mode == dill.FMODE_PICKLECONTENTS:
            assert open(fname).read() == "hello world!"
            assert f2mode == fmode
            assert f2tell == ftell
        else:
            raise RuntimeError("Uncovered file mode!")
        f2.close()

    # append

    trunc_file()

    f = open(fname, "a")
    f.write("hello")
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    fstr = open(fname).read()

    f = open(fname, "w")
    f.write("h")
    _ftell = f.tell()
    f.close()

    if safe_file:  # throw error if ftell > EOF
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        assert f2mode == fmode
        if file_mode == dill.FMODE_PRESERVEDATA:
            # position of writes cannot be changed on some OSs
            assert open(fname).read() == "h world!"
            assert f2tell == _ftell
        elif file_mode == dill.FMODE_NEWHANDLE:
            assert open(fname).read() == "h world!"
            assert f2tell == _ftell
        elif file_mode == dill.FMODE_PICKLECONTENTS:
            assert open(fname).read() == "hello world!"
            assert f2tell == ftell
        else:
            raise RuntimeError("Uncovered file mode!")
        f2.close()

    # file does not exist
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()
    f.close()

    os.remove(fname)

    if safe_file:  # throw error if file DNE
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        assert f2.mode == fmode
        if file_mode == dill.FMODE_PRESERVEDATA:
            # FIXME: this fails on systems where f2.tell() always returns 0
            # assert f2.tell() == ftell # 200
            assert f2.read() == ""
            f2.seek(0)
            assert f2.read() == ""
            assert f2.tell() == 0
        elif file_mode == dill.FMODE_PICKLECONTENTS:
            assert f2.tell() == ftell  # 200
            assert f2.read() == ""
            f2.seek(0)
            assert f2.read() == fstr
            assert f2.tell() == ftell  # 200
        elif file_mode == dill.FMODE_NEWHANDLE:
            assert f2.tell() == 0
            assert f2.read() == ""
            assert f2.tell() == 0
        else:
            raise RuntimeError("Uncovered file mode!")
        f2.close()

    # write

    write_randomness()

    f = open(fname, "w+")
    f.write("hello")
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    ftell = f.tell()
    fmode = f.mode
    f.close()

    os.remove(fname)

    if safe_file:  # throw error if file DNE
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        if file_mode == dill.FMODE_PRESERVEDATA:
            assert open(fname).read() == " world!"
            assert f2mode == 'w+'
            assert f2tell == 0
        elif file_mode == dill.FMODE_NEWHANDLE:
            assert open(fname).read() == " world!"
            assert f2mode == fmode
            assert f2tell == 0
        elif file_mode == dill.FMODE_PICKLECONTENTS:
            assert open(fname).read() == "hello world!"
            assert f2mode == fmode
            assert f2tell == ftell
        else:
            raise RuntimeError("Uncovered file mode!")

    # append

    trunc_file()

    f = open(fname, "a")
    f.write("hello")
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    ftell = f.tell()
    fmode = f.mode
    f.close()

    os.remove(fname)

    if safe_file:  # throw error if file DNE
        assert throws(dill.loads, (f_dumped,), IOError)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        assert f2mode == fmode
        if file_mode == dill.FMODE_PRESERVEDATA:
            assert open(fname).read() == " world!"
            assert f2tell == 0
        elif file_mode == dill.FMODE_NEWHANDLE:
            assert open(fname).read() == " world!"
            assert f2tell == 0
        elif file_mode == dill.FMODE_PICKLECONTENTS:
            assert open(fname).read() == "hello world!"
            assert f2tell == ftell
        else:
            raise RuntimeError("Uncovered file mode!")

    # file exists, with different contents (larger size)
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()
    f.close()
    _flen = 250
    _fstr = write_randomness(number=_flen)

    # XXX: no safe_file: no way to be 'safe'?

    f2 = dill.loads(f_dumped)
    assert f2.mode == fmode
    if file_mode == dill.FMODE_PRESERVEDATA:
        assert f2.tell() == ftell  # 200
        assert f2.read() == _fstr[ftell:]
        f2.seek(0)
        assert f2.read() == _fstr
        assert f2.tell() == _flen  # 250
    elif file_mode == dill.FMODE_NEWHANDLE:
        assert f2.tell() == 0
        assert f2.read() == _fstr
        assert f2.tell() == _flen  # 250
    elif file_mode == dill.FMODE_PICKLECONTENTS:
        assert f2.tell() == ftell  # 200
        assert f2.read() == ""
        f2.seek(0)
        assert f2.read() == fstr
        assert f2.tell() == ftell  # 200
    else:
        raise RuntimeError("Uncovered file mode!")
    f2.close()  # XXX: other alternatives?

    # write

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()

    fstr = open(fname).read()

    f.write(" and goodbye!")
    _ftell = f.tell()
    f.close()

    # XXX: no safe_file: no way to be 'safe'?

    f2 = dill.loads(f_dumped)
    f2mode = f2.mode
    f2tell = f2.tell()
    f2.write(" world!")
    f2.close()
    if file_mode == dill.FMODE_PRESERVEDATA:
        assert open(fname).read() == "hello world!odbye!"
        assert f2mode == 'r+'  # XXX: have to decide 'r+', 'a', ...?
        assert f2tell == ftell
    elif file_mode == dill.FMODE_NEWHANDLE:
        assert open(fname).read() == " world!"
        assert f2mode == fmode
        assert f2tell == 0
    elif file_mode == dill.FMODE_PICKLECONTENTS:
        assert open(fname).read() == "hello world!"
        assert f2mode == fmode
        assert f2tell == ftell
    else:
        raise RuntimeError("Uncovered file mode!")
    f2.close()

    # append

    trunc_file()

    f = open(fname, "a")
    f.write("hello")
    f_dumped = dill.dumps(f, safe_file=safe_file, file_mode=file_mode)
    fmode = f.mode
    ftell = f.tell()
    fstr = open(fname).read()

    f.write(" and goodbye!")
    _ftell = f.tell()
    f.close()

    # XXX: no safe_file: no way to be 'safe'?

    f2 = dill.loads(f_dumped)
    f2mode = f2.mode
    f2tell = f2.tell()
    f2.write(" world!")
    f2.close()
    assert f2mode == fmode
    if file_mode == dill.FMODE_PRESERVEDATA:
        assert open(fname).read() == "hello and goodbye! world!"
        assert f2tell == ftell
    elif file_mode == dill.FMODE_NEWHANDLE:
        assert open(fname).read() == "hello and goodbye! world!"
        assert f2tell == _ftell
    elif file_mode == dill.FMODE_PICKLECONTENTS:
        assert open(fname).read() == "hello world!"
        assert f2tell == ftell
    else:
        raise RuntimeError("Uncovered file mode!")
    f2.close()


test(safe_file=False, file_mode=dill.FMODE_NEWHANDLE)
test(safe_file=False, file_mode=dill.FMODE_PRESERVEDATA)
test(safe_file=False, file_mode=dill.FMODE_PICKLECONTENTS)
# TODO: switch this on when #57 is closed
# test(safe_file=True, file_mode=dill.FMODE_NEWHANDLE)
# test(safe_file=True, file_mode=dill.FMODE_PRESERVEDATA)
# test(safe_file=True, file_mode=dill.FMODE_PICKLECONTENTS)
if os.path.exists(fname):
    os.remove(fname)
