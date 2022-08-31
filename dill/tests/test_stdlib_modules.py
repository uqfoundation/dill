#!/usr/bin/env python

# Author: Leonardo Gama (@leogama)
# Copyright (c) 2022 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

import io
import itertools
import logging
import multiprocessing
import os
import sys
import warnings

import dill

if not dill._dill.OLD310:
    STDLIB_MODULES = list(sys.stdlib_module_names)
    STDLIB_MODULES += [
    # From https://docs.python.org/3.11/library/
    'collections.abc', 'concurrent.futures', 'curses.ascii', 'curses.panel', 'curses.textpad',
    'html.entities', 'html.parser', 'http.client', 'http.cookiejar', 'http.cookies', 'http.server',
    'importlib.metadata', 'importlib.resources', 'importlib.resources.abc', 'logging.config',
    'logging.handlers', 'multiprocessing.shared_memory', 'os.path', 'test.support',
    'test.support.bytecode_helper', 'test.support.import_helper', 'test.support.os_helper',
    'test.support.script_helper', 'test.support.socket_helper', 'test.support.threading_helper',
    'test.support.warnings_helper', 'tkinter.colorchooser', 'tkinter.dnd', 'tkinter.font',
    'tkinter.messagebox', 'tkinter.scrolledtext', 'tkinter.tix', 'tkinter.ttk', 'unittest.mock',
    'urllib.error', 'urllib.parse', 'urllib.request', 'urllib.response', 'urllib.robotparser',
    'xml.dom', 'xml.dom.minidom', 'xml.dom.pulldom', 'xml.etree.ElementTree', 'xml.parsers.expat',
    'xml.sax', 'xml.sax.handler', 'xml.sax.saxutils', 'xml.sax.xmlreader', 'xmlrpc.client',
    'xmlrpc.server',
    ]
    STDLIB_MODULES.sort()
else:
    STDLIB_MODULES = [
    # From https://docs.python.org/3.9/library/
    '__future__', '_thread', 'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio',
    'asyncore', 'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect', 'builtins',
    'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd', 'code', 'codecs', 'codeop',
    'collections', 'collections.abc', 'colorsys', 'compileall', 'concurrent', 'concurrent.futures',
    'configparser', 'contextlib', 'contextvars', 'copy', 'copyreg', 'crypt', 'csv', 'ctypes',
    'curses', 'curses.ascii', 'curses.panel', 'curses.textpad', 'dataclasses', 'datetime', 'dbm',
    'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email', 'ensurepip', 'enum', 'errno',
    'faulthandler', 'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'formatter', 'fractions', 'ftplib',
    'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib',
    'heapq', 'hmac', 'html', 'html.entities', 'html.parser', 'http', 'http.client',
    'http.cookiejar', 'http.cookies', 'http.server', 'imaplib', 'imghdr', 'imp', 'importlib',
    'importlib.metadata', 'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword', 'linecache',
    'locale', 'logging', 'logging.config', 'logging.handlers', 'lzma', 'mailbox', 'mailcap',
    'marshal', 'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib', 'msvcrt', 'multiprocessing',
    'multiprocessing.shared_memory', 'netrc', 'nis', 'nntplib', 'numbers', 'operator', 'optparse',
    'os', 'os.path', 'ossaudiodev', 'parser', 'pathlib', 'pdb', 'pickle', 'pickletools', 'pipes',
    'pkgutil', 'platform', 'plistlib', 'poplib', 'posix', 'pprint', 'pty', 'pwd', 'py_compile',
    'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline', 'reprlib', 'resource',
    'rlcompleter', 'runpy', 'sched', 'secrets', 'select', 'selectors', 'shelve', 'shlex', 'shutil',
    'signal', 'site', 'site', 'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd',
    'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess', 'sunau',
    'symbol', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile', 'telnetlib',
    'tempfile', 'termios', 'test', 'test.support', 'test.support.bytecode_helper',
    'test.support.script_helper', 'test.support.socket_helper', 'textwrap', 'threading', 'time',
    'timeit', 'tkinter', 'tkinter.colorchooser', 'tkinter.dnd', 'tkinter.font',
    'tkinter.messagebox', 'tkinter.scrolledtext', 'tkinter.tix', 'tkinter.ttk', 'token', 'tokenize',
    'trace', 'traceback', 'tracemalloc', 'tty', 'turtle', 'types', 'typing', 'unicodedata',
    'unittest', 'unittest.mock', 'urllib', 'urllib.error', 'urllib.parse', 'urllib.request',
    'urllib.response', 'urllib.robotparser', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
    'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml.dom', 'xml.dom.minidom',
    'xml.dom.pulldom', 'xml.etree.ElementTree', 'xml.parsers.expat', 'xml.sax', 'xml.sax.handler',
    'xml.sax.saxutils', 'xml.sax.xmlreader', 'xmlrpc', 'xmlrpc.client', 'xmlrpc.server', 'zipapp',
    'zipfile', 'zipimport', 'zlib', 'zoneinfo',
]

def _dump_load_module(module_name, refonfail):
    try:
        __import__(module_name)
    except ImportError:
        return None, None
    success_load = None
    buf = io.BytesIO()
    try:
        dill.dump_module(buf, module_name, refonfail=refonfail)
    except Exception:
        print("F", end="")
        success_dump = False
        return success_dump, success_load
    print(":", end="")
    success_dump = True
    buf.seek(0)
    try:
        module = dill.load_module(buf)
    except Exception:
        success_load = False
        return success_dump, success_load
    success_load = True
    return success_dump, success_load

def test_stdlib_modules():
    modules = [x for x in STDLIB_MODULES if
            not x.startswith('_')
            and not x.startswith('test')
            and x not in ('antigravity', 'this')]


    print("\nTesting pickling and unpickling of Standard Library modules...")
    message = "Success rate (%s_module, refonfail=%s): %.1f%% [%d/%d]"
    with multiprocessing.Pool(maxtasksperchild=1) as pool:
        for refonfail in (False, True):
            args = zip(modules, itertools.repeat(refonfail))
            result = pool.starmap(_dump_load_module, args, chunksize=1)
            dump_successes = sum(dumped for dumped, loaded in result if dumped is not None)
            load_successes = sum(loaded for dumped, loaded in result if loaded is not None)
            dump_failures = sum(not dumped for dumped, loaded in result if dumped is not None)
            load_failures = sum(not loaded for dumped, loaded in result if loaded is not None)
            dump_total = dump_successes + dump_failures
            load_total = load_successes + load_failures
            dump_percent = 100 * dump_successes / dump_total
            load_percent = 100 * load_successes / load_total
            print()
            print(message % ("dump", refonfail, dump_percent, dump_successes, dump_total))
            print(message % ("load", refonfail, load_percent, load_successes, load_total))
            if refonfail:
                failed_dump = [mod for mod, (dumped, _) in zip(modules, result) if dumped is False]
                failed_load = [mod for mod, (_, loaded) in zip(modules, result) if loaded is False]
                logging.info("dump_module() fails: %s", failed_dump)
                logging.info("load_module() fails: %s", failed_load)
                assert dump_percent > 95

if __name__ == '__main__':
    logging.basicConfig(level=os.environ.get('PYTHONLOGLEVEL', 'WARNING'))
    warnings.simplefilter('ignore')
    test_stdlib_modules()
