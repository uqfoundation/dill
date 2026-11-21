"""Source extraction for lambdas used inside expressions."""

import ast
import linecache
import warnings
from pathlib import Path
from types import MethodType
from unittest.mock import patch

from dill import temp
from dill.source import getblocks, getimport, getname, getsource, getsourcelines, importable


def capture(value):
    return value


def pick_second(_value, function):
    return function


wrapped = capture(lambda x: x + 1)
named = lambda x: x + 1
pair = (lambda: 1, lambda: 2)


def test_call_argument():
    source = getsource(wrapped)
    assert source == "lambda x: x + 1\n"
    assert eval(source)(2) == wrapped(2)


def test_decorator_argument():
    functions = []

    def decorator(function):
        functions.append(function)
        return lambda decorated: decorated

    @decorator(lambda: True)
    def decorated():
        pass

    source = getsource(functions[0])
    assert source == "lambda: True\n"
    assert eval(source)() is True
    assert 'decorated' not in source


def test_keyword_argument():
    function = capture(value=lambda: False)
    assert eval(getsource(function))() is False


def test_alias():
    function = capture(lambda: 42)
    namespace = {}
    exec(getsource(function, alias='answer'), namespace)
    assert namespace['answer']() == 42


def test_importable_alias():
    function = capture(lambda x: x * x)
    namespace = {}
    exec(importable(function, alias='square', source=True), namespace)
    assert namespace['square'](4) == 16


def test_multiline_argument():
    function = capture(
        lambda x:
            x + 1
    )
    source = getsource(function)
    assert isinstance(ast.parse(source).body[0].value, ast.Lambda)
    assert eval(source)(2) == 3


def test_unicode_prefix():
    function = pick_second('é', lambda: '你好')
    assert eval(getsource(function))() == '你好'


def test_closure_argument():
    offset = 3
    function = capture(lambda x: x + offset)
    assert eval(getsource(function), {'offset': offset})(2) == function(2)


def test_no_default_argument_execution():
    calls = []

    def default():
        calls.append(True)
        return 7

    function = capture(lambda value=default(): value)
    assert len(calls) == 1
    source = getsource(function, alias='function')
    ast.parse(source)
    assert 'default()' in source
    assert len(calls) == 1


def test_source_line_location():
    lines, position = getsourcelines(wrapped)
    assert position == wrapped.__code__.co_firstlineno - 1
    assert ''.join(lines) == getsource(wrapped)
    blocks, positions = getblocks(wrapped, locate=True)
    assert blocks == [lines]
    assert positions == [position]


def test_named_lambda_unchanged():
    assert getsource(named) == 'named = lambda x: x + 1\n'


def test_enclosing_source_unchanged():
    def factory(offset):
        return capture(lambda value: value + offset)

    source = getsource(factory(2), enclosing=True)
    assert 'def factory' in source
    assert 'return capture(lambda' in source


def test_ambiguous_source_unchanged():
    expected = 'pair = (lambda: 1, lambda: 2)\n'
    assert getsource(pair[0]) == expected
    assert getsource(pair[1]) == expected


def test_invalid_surrounding_source_unchanged():
    lines = Path(__file__).read_text().splitlines(keepends=True)
    lines.append('not valid Python !\n')
    with patch.object(linecache, 'getlines', return_value=lines):
        assert getsource(wrapped) == 'wrapped = capture(lambda x: x + 1)\n'


def test_bound_method():
    function = capture(lambda self, value: value + 1)
    method = MethodType(function, object())
    restored = MethodType(eval(getsource(method)), object())
    assert restored(2) == method(2)


def test_multiline_alias():
    function = capture(
        lambda value:
            value * 2
    )
    namespace = {}
    exec(getsource(function, alias='double'), namespace)
    assert namespace['double'](3) == 6


def test_defaults_with_colon():
    function = capture(lambda value={'answer': 42}: value)
    assert eval(getsource(function))() == function()


def test_wrapper_name_unchanged():
    assert getname(wrapped) == 'wrapped'


def test_wrapper_import_unchanged():
    namespace = {}
    exec(getimport(wrapped), namespace)
    assert namespace['wrapped'] is wrapped
    namespace = {}
    exec(importable(wrapped, source=False), namespace)
    assert namespace['wrapped'] is wrapped


def test_implicit_source_binding():
    namespace = {}
    exec(importable(wrapped, source=True), namespace)
    assert namespace['wrapped'](2) == wrapped(2)
    with temp.dumpIO_source(wrapped) as stream:
        assert temp.loadIO_source(stream)(2) == wrapped(2)


def test_source_parse_does_not_warn():
    lines = Path(__file__).read_text().splitlines(keepends=True)
    lines.append("unused = '\\d'\n")
    with patch.object(linecache, 'getlines', return_value=lines):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            filters = warnings.filters
            source = getsource(wrapped)
            assert warnings.filters is filters
        assert not caught
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            assert getsource(wrapped) == source


def test_variadic_lambda_location():
    function = capture(lambda*values: sum(values))
    source = getsource(function)
    assert eval(source)(1, 2) == function(1, 2)
    lines, position = getsourcelines(function)
    assert position == function.__code__.co_firstlineno - 1
    assert ''.join(lines) == source


def test_returned_lambda():
    def factory():
        return lambda value: value + 1

    assert eval(getsource(factory()))(2) == 3


def test_dictionary_lambda():
    functions = {'function': lambda: 42}
    assert eval(getsource(functions['function']))() == 42


def test_conditional_lambda():
    function = (lambda: 42) if True else None
    assert eval(getsource(function))() == 42


def test_formatted_string_lambda():
    functions = []

    def save(function):
        functions.append(function)
        return ''

    result = f"{save(lambda: 42)}"
    assert result == ''
    source = getsource(functions[0])
    if source.lstrip().startswith(('lambda', '(lambda')):
        assert eval(source)() == 42
    else:
        # Older AST positions may require the existing whole-statement fallback.
        assert 'result = f"{save(' in source


def test_multiline_keyword_argument():
    function = capture(
        value = lambda: False,
    )
    assert eval(getsource(function))() is False


def test_outermost_wrapper_unchanged():
    from dill.detect import outermost
    assert outermost(wrapped) is wrapped


def closure_factory():
    return capture(lambda value: value + 1)


def test_outermost_closure_unchanged():
    from dill.detect import outermost
    assert outermost(closure_factory()) is closure_factory


def test_derived_alias_stays_on_target():
    from dill.source import _closuredsource

    @capture
    def helper(value):
        return value + 1

    function = lambda value: helper(value) * 2
    blocks = _closuredsource(function)
    assert 'function = helper' not in blocks['helper'][1]


def test_missing_source_keeps_import_fallback():
    from dill.source import _closuredsource
    with patch('dill.source.getname', side_effect=IOError('source unavailable')):
        with patch('dill.source.getsource', return_value='from somewhere import function\n'):
            blocks = _closuredsource(wrapped)
    assert blocks[None] == ('', 'from somewhere import function\n')


if __name__ == '__main__':
    test_call_argument()
    test_decorator_argument()
    test_keyword_argument()
    test_alias()
    test_importable_alias()
    test_multiline_argument()
    test_unicode_prefix()
    test_closure_argument()
    test_no_default_argument_execution()
    test_source_line_location()
    test_named_lambda_unchanged()
    test_enclosing_source_unchanged()
    test_ambiguous_source_unchanged()
    test_invalid_surrounding_source_unchanged()
    test_bound_method()
    test_multiline_alias()
    test_defaults_with_colon()
    test_wrapper_name_unchanged()
    test_wrapper_import_unchanged()
    test_implicit_source_binding()
    test_source_parse_does_not_warn()
    test_variadic_lambda_location()
    test_returned_lambda()
    test_dictionary_lambda()
    test_conditional_lambda()
    test_formatted_string_lambda()
    test_multiline_keyword_argument()
    test_outermost_wrapper_unchanged()
    test_outermost_closure_unchanged()
    test_derived_alias_stays_on_target()
    test_missing_source_keeps_import_fallback()
