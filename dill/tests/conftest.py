"""Pytest configuration helpers for dill's legacy test suite."""

import logging
import os
import sys
from typing import Iterator

import pytest


_TEST_DIR = os.path.dirname(__file__)
if _TEST_DIR and _TEST_DIR not in sys.path:
    sys.path.insert(0, _TEST_DIR)


@pytest.fixture(params=[False, True])
def should_trace(request):
    """Toggle dill's pickling trace for logger tests."""

    from dill import detect
    from dill.logger import adapter as logger

    original_level = logger.logger.level
    detect.trace(request.param)
    try:
        yield request.param
    finally:
        detect.trace(False)
        logger.setLevel(original_level)


@pytest.fixture
def stream_trace() -> Iterator[str]:
    """Capture the trace output produced while pickling ``test_obj``."""

    from io import StringIO

    import dill
    from dill import detect
    from dill.logger import adapter as logger
    from dill.tests.test_logger import test_obj

    buffer = StringIO()
    handler = logging.StreamHandler(buffer)
    logger.addHandler(handler)
    original_level = logger.logger.level
    detect.trace(True)
    try:
        dill.dumps(test_obj)
        yield buffer.getvalue()
    finally:
        detect.trace(False)
        logger.removeHandler(handler)
        handler.close()
        logger.setLevel(original_level)
