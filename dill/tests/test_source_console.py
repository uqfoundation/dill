#!/usr/bin/env python
#
# Author: Ilya Khalafi (@IlyaKhalafi)
# Copyright (c) 2026 The Uncertainty Quantification Foundation.
# License: 3-clause BSD.  The full license text is available at:
#  - https://github.com/uqfoundation/dill/blob/master/LICENSE

from types import ModuleType
from unittest.mock import patch
import sys

from dill.source import findsource, getsource


class History(ModuleType):
    def __init__(self, lines):
        super().__init__('readline')
        self.lines = lines

    def get_current_history_length(self):
        return len(self.lines)

    def get_history_item(self, index):
        return self.lines[index - 1]


def test_console_with_bootstrap_file():
    for filename in ('<console>', '<stdin>', '<python-input-4>'):
        for reader in ('readline', 'pyrepl'):
            source = 'def squared(x):\n    return x*x\n'
            main = ModuleType('__main__')
            main.__file__ = __file__
            exec(compile(source, filename, 'exec'), main.__dict__)
            entries = [source.rstrip('\n')] if reader == 'pyrepl' else source.splitlines()
            history = History(['unrelated = 1'] + entries)
            pyrepl = ModuleType('_pyrepl.readline')
            pyrepl._wrapper = history
            modules = {'__main__': main, 'readline': history,
                       '_pyrepl.readline': pyrepl if reader == 'pyrepl' else None}
            with patch.dict(sys.modules, modules):
                lines, start = findsource(main.squared)
                assert ''.join(lines[start:]) == source, (filename, reader)
                assert getsource(main.squared) == source, (filename, reader)
                assert getsource(main.squared, alias='copied') == (
                    source + '\ncopied = squared\n'), (filename, reader)


def test_file_backed_main_is_not_interactive():
    main = ModuleType('__main__')
    main.__file__ = __file__
    function_source = 'def real_file_function():\n    return 1\n'
    class_source = 'class RealFileClass:\n    pass\n'
    source = function_source + '\n' + class_source
    lines = source.splitlines(keepends=True)
    exec(compile(source, __file__, 'exec'), main.__dict__)
    with patch.dict(sys.modules, {'__main__': main}), \
         patch('dill.source.linecache.getlines', return_value=lines):
        assert getsource(main.real_file_function) == function_source
        assert getsource(main.RealFileClass) == class_source
        found, start = findsource(main.RealFileClass())
        assert ''.join(found[start:]) == class_source


if __name__ == '__main__':
    test_console_with_bootstrap_file()
    test_file_backed_main_is_not_interactive()
