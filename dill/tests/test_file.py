#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import os
import sys
import string
import random

import dill


dill.settings['recurse'] = True

fname = "_test_file.txt"
rand_chars = list(string.ascii_letters) + ["\n"] * 40  # bias newline

buffer_error = ValueError("invalid buffer size")
dne_error = FileNotFoundError("[Errno 2] No such file or directory: '%s'" % fname)


def write_randomness(number=200):
    f = open(fname, "w")
    for i in range(number):
        f.write(random.choice(rand_chars))
    f.close()
    f = open(fname, "r")
    contents = f.read()
    f.close()
    return contents


def trunc_file():
    open(fname, "w").close()


def throws(op, args, exc):
    try:
        op(*args)
    except type(exc):
        return sys.exc_info()[1].args == exc.args
    else:
        return False


def teardown_module():
    if os.path.exists(fname):
        os.remove(fname)


def bench(strictio, fmode, skippypy):
    import platform
    if skippypy and platform.python_implementation() == 'PyPy':
        # Skip for PyPy...
        return

    # file exists, with same contents
    # read

    write_randomness()

    f = open(fname, "r")
    _f = dill.loads(dill.dumps(f, fmode=fmode))#, strictio=strictio))
    assert _f.mode == f.mode
    assert _f.tell() == f.tell()
    assert _f.read() == f.read()
    f.close()
    _f.close()

    # write

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
    ftell = f.tell()
    f.close()
    f2 = dill.loads(f_dumped) #FIXME: fails due to pypy/issues/1233
    # TypeError: expected py_object instance instead of str
    f2mode = f2.mode
    f2tell = f2.tell()
    f2name = f2.name
    f2.write(" world!")
    f2.close()

    if fmode == dill.HANDLE_FMODE:
        assert open(fname).read() == " world!"
        assert f2mode == f1mode
        assert f2tell == 0
    elif fmode == dill.CONTENTS_FMODE:
        assert open(fname).read() == "hello world!"
        assert f2mode == f1mode
        assert f2tell == ftell
        assert f2name == fname
    elif fmode == dill.FILE_FMODE:
        assert open(fname).read() == "hello world!"
        assert f2mode == f1mode
        assert f2tell == ftell
    else:
        raise RuntimeError("Unknown file mode '%s'" % fmode)

    # append

    trunc_file()

    f = open(fname, "a")
    f.write("hello")
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
    ftell = f.tell()
    f.close()
    f2 = dill.loads(f_dumped)
    f2mode = f2.mode
    f2tell = f2.tell()
    f2.write(" world!")
    f2.close()

    assert f2mode == f1mode
    if fmode == dill.CONTENTS_FMODE:
        assert open(fname).read() == "hello world!"
        assert f2tell == ftell
    elif fmode == dill.HANDLE_FMODE:
        assert open(fname).read() == "hello world!"
        assert f2tell == ftell
    elif fmode == dill.FILE_FMODE:
        assert open(fname).read() == "hello world!"
        assert f2tell == ftell
    else:
        raise RuntimeError("Unknown file mode '%s'" % fmode)

    # file exists, with different contents (smaller size)
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
    ftell = f.tell()
    f.close()
    _flen = 150
    _fstr = write_randomness(number=_flen)

    if strictio:  # throw error if ftell > EOF
        assert throws(dill.loads, (f_dumped,), buffer_error)
    else:
        f2 = dill.loads(f_dumped)
        assert f2.mode == f1mode
        if fmode == dill.CONTENTS_FMODE:
            assert f2.tell() == _flen
            assert f2.read() == ""
            f2.seek(0)
            assert f2.read() == _fstr
            assert f2.tell() == _flen  # 150
        elif fmode == dill.HANDLE_FMODE:
            assert f2.tell() == 0
            assert f2.read() == _fstr
            assert f2.tell() == _flen  # 150
        elif fmode == dill.FILE_FMODE:
            assert f2.tell() == ftell  # 200
            assert f2.read() == ""
            f2.seek(0)
            assert f2.read() == fstr
            assert f2.tell() == ftell  # 200
        else:
            raise RuntimeError("Unknown file mode '%s'" % fmode)
        f2.close()

    # write

    write_randomness()

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
    ftell = f.tell()
    f.close()
    fstr = open(fname).read()

    f = open(fname, "w")
    f.write("h")
    _ftell = f.tell()
    f.close()

    if strictio:  # throw error if ftell > EOF
        assert throws(dill.loads, (f_dumped,), buffer_error)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        if fmode == dill.CONTENTS_FMODE:
            assert open(fname).read() == "h world!"
            assert f2mode == f1mode
            assert f2tell == _ftell
        elif fmode == dill.HANDLE_FMODE:
            assert open(fname).read() == " world!"
            assert f2mode == f1mode
            assert f2tell == 0
        elif fmode == dill.FILE_FMODE:
            assert open(fname).read() == "hello world!"
            assert f2mode == f1mode
            assert f2tell == ftell
        else:
            raise RuntimeError("Unknown file mode '%s'" % fmode)
        f2.close()

    # append

    trunc_file()

    f = open(fname, "a")
    f.write("hello")
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
    ftell = f.tell()
    f.close()
    fstr = open(fname).read()

    f = open(fname, "w")
    f.write("h")
    _ftell = f.tell()
    f.close()

    if strictio:  # throw error if ftell > EOF
        assert throws(dill.loads, (f_dumped,), buffer_error)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        assert f2mode == f1mode
        if fmode == dill.CONTENTS_FMODE:
            # position of writes cannot be changed on some OSs
            assert open(fname).read() == "h world!"
            assert f2tell == _ftell
        elif fmode == dill.HANDLE_FMODE:
            assert open(fname).read() == "h world!"
            assert f2tell == _ftell
        elif fmode == dill.FILE_FMODE:
            assert open(fname).read() == "hello world!"
            assert f2tell == ftell
        else:
            raise RuntimeError("Unknown file mode '%s'" % fmode)
        f2.close()

    # file does not exist
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
    ftell = f.tell()
    f.close()

    os.remove(fname)

    if strictio:  # throw error if file DNE
        assert throws(dill.loads, (f_dumped,), dne_error)
    else:
        f2 = dill.loads(f_dumped)
        assert f2.mode == f1mode
        if fmode == dill.CONTENTS_FMODE:
            # FIXME: this fails on systems where f2.tell() always returns 0
            # assert f2.tell() == ftell # 200
            assert f2.read() == ""
            f2.seek(0)
            assert f2.read() == ""
            assert f2.tell() == 0
        elif fmode == dill.FILE_FMODE:
            assert f2.tell() == ftell  # 200
            assert f2.read() == ""
            f2.seek(0)
            assert f2.read() == fstr
            assert f2.tell() == ftell  # 200
        elif fmode == dill.HANDLE_FMODE:
            assert f2.tell() == 0
            assert f2.read() == ""
            assert f2.tell() == 0
        else:
            raise RuntimeError("Unknown file mode '%s'" % fmode)
        f2.close()

    # write

    write_randomness()

    f = open(fname, "w+")
    f.write("hello")
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    ftell = f.tell()
    f1mode = f.mode
    f.close()

    os.remove(fname)

    if strictio:  # throw error if file DNE
        assert throws(dill.loads, (f_dumped,), dne_error)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        if fmode == dill.CONTENTS_FMODE:
            assert open(fname).read() == " world!"
            assert f2mode == 'w+'
            assert f2tell == 0
        elif fmode == dill.HANDLE_FMODE:
            assert open(fname).read() == " world!"
            assert f2mode == f1mode
            assert f2tell == 0
        elif fmode == dill.FILE_FMODE:
            assert open(fname).read() == "hello world!"
            assert f2mode == f1mode
            assert f2tell == ftell
        else:
            raise RuntimeError("Unknown file mode '%s'" % fmode)

    # append

    trunc_file()

    f = open(fname, "a")
    f.write("hello")
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    ftell = f.tell()
    f1mode = f.mode
    f.close()

    os.remove(fname)

    if strictio:  # throw error if file DNE
        assert throws(dill.loads, (f_dumped,), dne_error)
    else:
        f2 = dill.loads(f_dumped)
        f2mode = f2.mode
        f2tell = f2.tell()
        f2.write(" world!")
        f2.close()
        assert f2mode == f1mode
        if fmode == dill.CONTENTS_FMODE:
            assert open(fname).read() == " world!"
            assert f2tell == 0
        elif fmode == dill.HANDLE_FMODE:
            assert open(fname).read() == " world!"
            assert f2tell == 0
        elif fmode == dill.FILE_FMODE:
            assert open(fname).read() == "hello world!"
            assert f2tell == ftell
        else:
            raise RuntimeError("Unknown file mode '%s'" % fmode)

    # file exists, with different contents (larger size)
    # read

    write_randomness()

    f = open(fname, "r")
    fstr = f.read()
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
    ftell = f.tell()
    f.close()
    _flen = 250
    _fstr = write_randomness(number=_flen)

    # XXX: no safe_file: no way to be 'safe'?

    f2 = dill.loads(f_dumped)
    assert f2.mode == f1mode
    if fmode == dill.CONTENTS_FMODE:
        assert f2.tell() == ftell  # 200
        assert f2.read() == _fstr[ftell:]
        f2.seek(0)
        assert f2.read() == _fstr
        assert f2.tell() == _flen  # 250
    elif fmode == dill.HANDLE_FMODE:
        assert f2.tell() == 0
        assert f2.read() == _fstr
        assert f2.tell() == _flen  # 250
    elif fmode == dill.FILE_FMODE:
        assert f2.tell() == ftell  # 200
        assert f2.read() == ""
        f2.seek(0)
        assert f2.read() == fstr
        assert f2.tell() == ftell  # 200
    else:
        raise RuntimeError("Unknown file mode '%s'" % fmode)
    f2.close()  # XXX: other alternatives?

    # write

    f = open(fname, "w")
    f.write("hello")
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
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
    if fmode == dill.CONTENTS_FMODE:
        assert open(fname).read() == "hello world!odbye!"
        assert f2mode == f1mode
        assert f2tell == ftell
    elif fmode == dill.HANDLE_FMODE:
        assert open(fname).read() == " world!"
        assert f2mode == f1mode
        assert f2tell == 0
    elif fmode == dill.FILE_FMODE:
        assert open(fname).read() == "hello world!"
        assert f2mode == f1mode
        assert f2tell == ftell
    else:
        raise RuntimeError("Unknown file mode '%s'" % fmode)
    f2.close()

    # append

    trunc_file()

    f = open(fname, "a")
    f.write("hello")
    f_dumped = dill.dumps(f, fmode=fmode)#, strictio=strictio)
    f1mode = f.mode
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
    assert f2mode == f1mode
    if fmode == dill.CONTENTS_FMODE:
        assert open(fname).read() == "hello and goodbye! world!"
        assert f2tell == ftell
    elif fmode == dill.HANDLE_FMODE:
        assert open(fname).read() == "hello and goodbye! world!"
        assert f2tell == _ftell
    elif fmode == dill.FILE_FMODE:
        assert open(fname).read() == "hello world!"
        assert f2tell == ftell
    else:
        raise RuntimeError("Unknown file mode '%s'" % fmode)
    f2.close()


def test_nostrictio_handlefmode():
    bench(False, dill.HANDLE_FMODE, False)
    teardown_module()


def test_nostrictio_filefmode():
    bench(False, dill.FILE_FMODE, False)
    teardown_module()


def test_nostrictio_contentsfmode():
    bench(False, dill.CONTENTS_FMODE, True)
    teardown_module()


def test_recreated_file_permissions():
    # a file recreated from a pickled handle must not be group/other
    # accessible or executable
    import platform
    if os.name != 'posix' or platform.python_implementation() == 'PyPy':
        return
    pname = "_test_perms.txt"
    old_umask = os.umask(0o022)  # a permissive umask exposes the missing mode
    try:
        f = open(pname, "w")
        f.write("secret")
        dumped = dill.dumps(f, fmode=dill.CONTENTS_FMODE)
        f.close()
        os.remove(pname)  # force recreation on load (the file-transfer case)
        f2 = dill.loads(dumped)
        f2.close()
        bits = os.stat(pname).st_mode & 0o777
        assert bits & 0o177 == 0, "recreated file is world-accessible: %o" % bits
    finally:
        os.umask(old_umask)
        if os.path.exists(pname):
            os.remove(pname)


def test_binary_file_contents():
    import tempfile
    from pathlib import Path

    contents = bytes(range(256))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'binary.dat'
        for protocol in range(dill.HIGHEST_PROTOCOL + 1):
            for mode in ('rb', 'r+b', 'wb', 'w+b', 'ab', 'a+b'):
                path.write_bytes(contents)
                with path.open(mode) as stream:
                    if 'w' in mode:
                        stream.write(contents)
                    stream.seek(2)
                    expected_mode = stream.mode
                    dumped = dill.dumps(stream, protocol=protocol,
                                        fmode=dill.FILE_FMODE)
                path.write_bytes(b'changed')

                with dill.loads(dumped) as restored:
                    assert restored.mode == expected_mode
                    assert restored.tell() == 2
                    restored.flush()
                    assert path.read_bytes() == contents
                    if 'r' in mode or '+' in mode:
                        assert restored.read() == contents[2:]


def test_legacy_binary_file_contents():
    import tempfile
    from pathlib import Path

    class LegacyFile:
        def __reduce__(self):
            return (dill._dill._create_filehandle,
                    (str(path), 'rb', 2, False, open, False,
                     dill.FILE_FMODE, 'legacy content'))

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'legacy.dat'
        dumped = dill.dumps(LegacyFile())
        with dill.loads(dumped) as restored:
            assert restored.mode == 'rb'
            assert restored.tell() == 2
            assert restored.read() == b'gacy content'


#bench(True, dill.HANDLE_FMODE, False)
#bench(True, dill.FILE_FMODE, False)
#bench(True, dill.CONTENTS_FMODE, True)


if __name__ == '__main__':
    test_nostrictio_handlefmode()
    test_nostrictio_filefmode()
    test_nostrictio_contentsfmode()
    test_recreated_file_permissions()
    test_binary_file_contents()
    test_legacy_binary_file_contents()
