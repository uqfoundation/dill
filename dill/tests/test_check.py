#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Copyright (c) 2008-2016 California Institute of Technology.
# Copyright (c) 2016-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from dill import check
import sys

from dill.temp import capture


#FIXME: this doesn't catch output... it's from the internal call
def raise_check(func, **kwds):
    try:
        with capture('stdout') as out:
            check(func, **kwds)
    except Exception:
        e = sys.exc_info()[1]
        raise AssertionError(str(e))
    else:
        assert 'Traceback' not in out.getvalue()
    finally:
        out.close()


f = lambda x:x**2


def test_simple(verbose=None):
    raise_check(f, verbose=verbose)


def test_recurse(verbose=None):
    raise_check(f, recurse=True, verbose=verbose)


def test_byref(verbose=None):
    raise_check(f, byref=True, verbose=verbose)


def test_protocol(verbose=None):
    raise_check(f, protocol=True, verbose=verbose)


def test_python(verbose=None):
    raise_check(f, python=None, verbose=verbose)


def test_python_path_with_spaces():
    import dill
    import os
    import subprocess
    import tempfile
    import venv
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix='dill check ') as directory:
        venv.EnvBuilder(with_pip=False, system_site_packages=True).create(directory)
        executable = Path(directory) / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        site_packages = subprocess.check_output(
            [str(executable), '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'], text=True
        ).strip()
        (Path(site_packages) / 'dill-test.pth').write_text(
            str(Path(dill.__file__).resolve().parent.parent) + '\n', encoding='utf-8'
        )
        with capture('stdout') as output:
            check({'answer': 42}, python=str(executable), verbose=True)
        assert 'SUCCESS' in output.getvalue()
        assert 'LOAD FAILED' not in output.getvalue()


#TODO: test incompatible versions
#TODO: test dump failure
#TODO: test load failure


if __name__ == '__main__':
    test_simple()
    test_recurse()
    test_byref()
    test_protocol()
    test_python()
    test_python_path_with_spaces()
