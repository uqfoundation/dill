#!/usr/bin/env python
#
# Author: Mike McKerns (mmckerns @caltech and @uqfoundation)
# Author: Anirudh Vegesana (avegesan@cs.stanford.edu)
# Copyright (c) 2022-2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE
"""
test pickling a PyCapsule object
"""

import dill
import warnings

test_pycapsule = None
test_pycapsule_nested_name = None

if dill._dill._testcapsule is not None:
    import ctypes
    def test_pycapsule():
        name = ctypes.create_string_buffer(b'dill._testcapsule')
        capsule = dill._dill._PyCapsule_New(
            ctypes.cast(dill._dill._PyCapsule_New, ctypes.c_void_p),
            name,
            None
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dill.copy(capsule)
        dill._testcapsule = capsule
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dill.copy(capsule)
        dill._testcapsule = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", dill.PicklingWarning)
                dill.copy(capsule)
        except dill.UnpicklingError:
            pass
        else:
            raise AssertionError("Expected a different error")

    def test_pycapsule_nested_name():
        # a capsule name with more than one dot has to be resolved by importing
        # the top-level module and walking the remaining attributes; otherwise
        # the owning object is never found and the capsule is rebuilt from the
        # raw pointer recorded at dump time.
        name = ctypes.create_string_buffer(b'dill._dill._nested_testcapsule')
        capsule = dill._dill._PyCapsule_New(
            ctypes.cast(dill._dill._PyCapsule_New, ctypes.c_void_p),
            name,
            None
        )
        dill._dill._nested_testcapsule = capsule
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                assert dill.copy(capsule) is capsule
        finally:
            del dill._dill._nested_testcapsule

if __name__ == '__main__':
    if test_pycapsule is not None:
        test_pycapsule()
        test_pycapsule_nested_name()
