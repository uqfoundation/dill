from types import ModuleType
from unittest.mock import patch
import linecache
import sys

from dill.source import findsource, getsourcelines, getsource


class History(ModuleType):
    def __init__(self, lines):
        super().__init__('readline')
        self.lines = lines

    def get_current_history_length(self):
        return len(self.lines)

    def get_history_item(self, index):
        return self.lines[index - 1]


def test_interactive_async_source():
    # The readline API also allows history to be populated one line at a time.
    definitions = (
        'async def squared(x):\n    return x*x\n',
        'async def squared(x):\n    yield x*x\n',
        '@decorate\nasync def squared(x):\n    return x*x\n',
        'async def squared(x=lambda: 1):\n    return x()\n',
        'async\tdef squared(x=lambda: 1):\n    return x()\n',
    )
    for source in definitions:
        for filename in ('<stdin>', '<python-input-4>'):
            for reader in ('readline', 'pyrepl'):
                main = ModuleType('__main__')
                main.decorate = lambda func: func
                exec(compile(source, filename, 'exec'), main.__dict__)
                prefix = 'unrelated = 1\n'
                history = History((prefix + source + '\n').splitlines())
                pyrepl = ModuleType('_pyrepl.readline')
                pyrepl._wrapper = history
                modules = {'__main__': main, 'readline': history,
                           '_pyrepl.readline': pyrepl if reader == 'pyrepl' else None}
                with patch.dict(sys.modules, modules):
                    lines, start = findsource(main.squared)
                    assert start == 1, (source, filename, reader)
                    assert ''.join(lines[start:]).rstrip() == source.rstrip()
                    assert getsourcelines(main.squared) == (source.splitlines(True), 1)
                    assert getsource(main.squared) == source
                    assert getsource(main.squared, alias='copied') == (
                        source + '\ncopied = squared\n')


def test_interactive_names_match_the_definition():
    for name in ('sync', 's', 'a', 'f', 'a\u034f'):
        source = 'def %s():\n    return 1\n' % name
        later = 'async def unrelated():\n    return 2\n'
        main = ModuleType('__main__')
        exec(compile(source + later, '<stdin>', 'exec'), main.__dict__)
        history = History(('marker = 1\n' + source + '\n' + later).splitlines())
        modules = {'__main__': main, 'readline': history, '_pyrepl.readline': None}
        with patch.dict(sys.modules, modules):
            assert getsource(getattr(main, name)) == source, name


def test_pyrepl_async_block_entry():
    source = 'async def squared(x):\n    return x*x\n'
    main = ModuleType('__main__')
    exec(compile(source, '<python-input-4>', 'exec'), main.__dict__)
    history = History(['marker = 1', source.rstrip('\n')])
    pyrepl = ModuleType('_pyrepl.readline')
    pyrepl._wrapper = history
    with patch.dict(sys.modules, {'__main__': main, '_pyrepl.readline': pyrepl}):
        assert getsource(main.squared) == source


def test_cached_code_object_matches_the_definition():
    source = 'def sync():\n    return 1\n'
    cell = 'marker = 1\n' + source + '\nasync def unrelated():\n    return 2\n'
    filename = '<ipython-input-123-async-source>'
    namespace = {}
    exec(compile(cell, filename, 'exec'), namespace)
    entry = (len(cell), None, cell.splitlines(True), filename)
    with patch.dict(linecache.cache, {filename: entry}):
        assert getsource(namespace['sync'].__code__) == source


def test_pyrepl_nested_block_entry():
    source = 'def outer():\n    def inner():\n        return 1\n    return inner\n'
    main = ModuleType('__main__')
    exec(compile(source, '<python-input-5>', 'exec'), main.__dict__)
    history = History(['marker = 1', source.rstrip('\n'), 'inner = outer()'])
    pyrepl = ModuleType('_pyrepl.readline')
    pyrepl._wrapper = history
    with patch.dict(sys.modules, {'__main__': main, '_pyrepl.readline': pyrepl}):
        assert getsource(main.outer(), enclosing=True) == source


def test_pyrepl_decorated_code_entry():
    source = '@decorate\ndef target():\n    return 1\n'
    main = ModuleType('__main__')
    main.decorate = lambda func: func
    exec(compile(source, '<python-input-6>', 'exec'), main.__dict__)
    history = History(['marker = 1', source.rstrip('\n')])
    pyrepl = ModuleType('_pyrepl.readline')
    pyrepl._wrapper = history
    with patch.dict(sys.modules, {'__main__': main, '_pyrepl.readline': pyrepl}), \
         patch('dill.source.getmodule', return_value=main):
        assert getsource(main.target.__code__) == source


def test_continued_definition_names():
    for source in ('def sync \\\n():\n    return 1\n', 'def \\\nf():\n    return 1\n'):
        name = 'sync' if 'sync' in source else 'f'
        main = ModuleType('__main__')
        exec(compile(source, '<stdin>', 'exec'), main.__dict__)
        history = History(('marker = 1\n' + source).splitlines())
        with patch.dict(sys.modules, {'__main__': main, 'readline': history,
                                     '_pyrepl.readline': None}):
            assert getsource(getattr(main, name)) == source


async def async_outer():
    async def nested():
        return 1
    return nested


class AsyncMethods:
    async def method(self):
        return 1


def test_file_async_method_source():
    expected = '    async def method(self):\n        return 1\n'
    assert getsource(AsyncMethods.method) == expected
    assert getsource(AsyncMethods().method) == expected


def test_file_async_enclosing_source():
    import asyncio
    nested = asyncio.run(async_outer())
    source = getsource(nested, enclosing=True)
    assert source.startswith('async def async_outer():\n'), source
    assert 'async def nested():' in source
    assert 'return nested' in source
    assert getsource(nested, alias='copied') == (
        'async def nested():\n    return 1\n\ncopied = nested\n')


if __name__ == '__main__':
    test_interactive_async_source()
    test_interactive_names_match_the_definition()
    test_pyrepl_async_block_entry()
    test_cached_code_object_matches_the_definition()
    test_pyrepl_nested_block_entry()
    test_pyrepl_decorated_code_entry()
    test_continued_definition_names()
    test_file_async_method_source()
    test_file_async_enclosing_source()
