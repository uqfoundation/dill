"""Source exports must not overwrite unrelated names in their destination."""

import builtins

from dill.source import importable


def offset_factory(offset):
    def add_offset(value):
        return value + offset
    return add_offset


def nested_factory(first):
    def middle(second):
        def result(value):
            return first + second + value
        return result
    return middle


def plain(value):
    return value + 1


GLOBAL_COUNT = 3


def read_count():
    return GLOBAL_COUNT


def increment_count():
    global GLOBAL_COUNT
    GLOBAL_COUNT += 1
    return GLOBAL_COUNT


def use_functions(first, second):
    def result():
        return first(), second()
    return result


def factorial(value):
    return 1 if value == 0 else value * factorial(value - 1)


STRING_PREFIX = "prefix:"


def multiline_string():
    return STRING_PREFIX + """first
  second
third"""



def builtin_factory(function):
    def result(value):
        return function(value) + value
    return result


def restore(function, alias, namespace=None):
    if namespace is None:
        namespace = {}
    source = importable(function, alias=alias, source=True)
    exec(source, namespace)
    return namespace[alias], namespace


def test_namespace():
    sentinel = object()
    namespace = {"offset":sentinel, "add_offset":sentinel}
    first, _ = restore(offset_factory(1), "add_one", namespace)
    second, _ = restore(offset_factory(10), "add_ten", namespace)
    assert first(0) == 1
    assert second(0) == 10
    assert namespace["offset"] is sentinel
    assert namespace["add_offset"] is sentinel
    assert set(namespace) == {
        "__builtins__", "offset", "add_offset", "add_one", "add_ten",
    }


def test_default_name():
    sentinel = object()
    namespace = {"offset":sentinel}
    function = offset_factory(7)
    exec(importable(function, source=True), namespace)
    assert namespace["add_offset"](2) == 9
    assert namespace["offset"] is sentinel
    assert set(namespace) == {"__builtins__", "offset", "add_offset"}


def test_aliases():
    for alias in ("plain", "exec", "globals", "namespace", "offset", "résultat"):
        sentinel = object()
        namespace = {"plain":sentinel, "exec":sentinel, "globals":sentinel}
        before = dict(namespace)
        result, namespace = restore(plain, alias, namespace)
        assert result(2) == 3
        for name, value in before.items():
            if name != alias:
                assert namespace[name] is value
        assert set(namespace) == set(before) | {"__builtins__", alias}



def uses_builtin(value):
    return len(value)


def test_metadata_aliases():
    for alias in ("__builtins__", "__name__", "__package__"):
        namespace = {
            "__name__":"destination",
            "__package__":"example",
            "__builtins__":vars(builtins),
        }
        before = dict(namespace)
        restored, namespace = restore(uses_builtin, alias, namespace)
        assert restored([1, 2]) == 2
        assert restored.__module__ == "destination"
        for name, value in before.items():
            if name != alias:
                assert namespace[name] is value
        assert set(namespace) == set(before)


def test_nested_closure():
    result, namespace = restore(nested_factory(2)(3), "exported")
    assert result(4) == 9
    assert set(namespace) == {"__builtins__", "exported"}


def test_global_reads_and_writes():
    sentinel = object()
    namespace = {"GLOBAL_COUNT":sentinel}
    reader, _ = restore(read_count, "reader", namespace)
    writer, _ = restore(increment_count, "writer", namespace)
    assert reader() == 3
    assert writer() == 4
    assert writer() == 5
    assert reader() == 3
    assert namespace["GLOBAL_COUNT"] is sentinel
    assert set(namespace) == {"__builtins__", "GLOBAL_COUNT", "reader", "writer"}


def test_shared_dependencies():
    function = use_functions(increment_count, read_count)
    result, namespace = restore(function, "exported")
    assert result() == (4, 4)
    assert result() == (5, 5)
    assert set(namespace) == {"__builtins__", "exported"}


def test_recursion():
    result, namespace = restore(factorial, "product")
    assert result(6) == 720
    assert set(namespace) == {"__builtins__", "product"}


def test_multiline_string():
    result, namespace = restore(multiline_string, "exported")
    assert result() == "prefix:first\n  second\nthird"
    assert set(namespace) == {"__builtins__", "exported"}


def test_module_context():
    namespace = {
        "__name__":"destination",
        "__package__":"example",
        "__builtins__":vars(builtins),
        "unrelated":object(),
    }
    result, namespace = restore(offset_factory(5), "exported", namespace)
    assert result(2) == 7
    assert result.__module__ == "destination"
    assert result.__globals__["__package__"] == "example"
    assert result.__globals__["__builtins__"] is vars(builtins)
    assert "unrelated" not in result.__globals__


def test_separate_locals():
    globals_ = {"__name__":"destination"}
    locals_ = {}
    exec(importable(offset_factory(5), alias="exported", source=True),
         globals_, locals_)
    assert locals_["exported"](1) == 6
    assert set(locals_) == {"exported"}
    assert set(globals_) == {"__builtins__", "__name__"}




def test_builtin_dependency():
    import math
    for dependency in (math.sin, abs):
        original = builtin_factory(dependency)
        restored, namespace = restore(original, "exported")
        assert restored is not original
        assert restored(-2) == original(-2)
        assert set(namespace) == {"__builtins__", "exported"}


def test_temp_roundtrips():
    from dill import temp
    function = offset_factory(7)
    with temp.dumpIO_source(function, alias="exported") as stream:
        restored = temp.loadIO_source(stream)
        assert restored(2) == 9
    with temp.dump_source(function, alias="exported") as stream:
        restored = temp.load_source(stream)
        assert restored(2) == 9


class ForwardReference:
    child: "ForwardReference"


def test_class_alias_compatibility():
    import sys
    import types
    import typing
    module = types.ModuleType("_dill_source_class_namespace")
    sys.modules[module.__name__] = module
    try:
        exec(importable(ForwardReference, alias="Exported", source=True),
             vars(module))
        hints = typing.get_type_hints(module.Exported)
        assert hints["child"] is module.Exported
        assert module.ForwardReference is module.Exported
    finally:
        del sys.modules[module.__name__]



def test_source_analysis_does_not_warn():
    import importlib.util
    from pathlib import Path
    import sys
    from tempfile import TemporaryDirectory
    import warnings
    name = "_dill_source_escape"
    with TemporaryDirectory() as directory:
        path = Path(directory, name + ".py")
        path.write_text("def function():\n    return '" + chr(92) + "d'\n")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                warnings.simplefilter("ignore", DeprecationWarning)
                spec.loader.exec_module(module)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("error")
                source = importable(module.function, alias="exported", source=True)
            assert not caught
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                warnings.simplefilter("ignore", DeprecationWarning)
                namespace = {}
                exec(source, namespace)
            assert namespace["exported"]() == chr(92) + "d"
            assert set(namespace) == {"__builtins__", "exported"}
        finally:
            sys.modules.pop(name, None)


def test_imports_and_plain_source():
    assert importable(plain, source=False) == "from %s import plain\n" % __name__
    assert importable(plain, source=True) == (
        "def plain(value):\n    return value + 1\n"
    )
    assert importable(100, alias="number", source=True) == "number = 100\n"


if __name__ == "__main__":
    test_namespace()
    test_default_name()
    test_aliases()
    test_nested_closure()
    test_metadata_aliases()
    test_global_reads_and_writes()
    test_shared_dependencies()
    test_recursion()
    test_multiline_string()
    test_module_context()
    test_separate_locals()
    test_imports_and_plain_source()
    test_source_analysis_does_not_warn()
    test_temp_roundtrips()
    test_builtin_dependency()
    test_class_alias_compatibility()
