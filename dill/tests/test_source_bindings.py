"""Module binding analysis must follow Python's scope boundaries."""

import ast

from dill.source import _source_binding_names


def bindings(source):
    return _source_binding_names(ast.parse(source))


def test_assignments_and_imports():
    source = """
import os.path
import json as codec
from math import sin as sine, cos
first, *rest = values
annotated: int
counter += 1
del removed
object.attribute = 1
object[index] = 2
"""
    assert bindings(source) == {
        "os", "codec", "sine", "cos", "first", "rest", "annotated",
        "counter", "removed",
    }


def test_control_flow():
    source = """
if condition:
    conditional = 1
else:
    alternative = 2
for first, second in pairs:
    loop = first
with resource() as opened:
    context = opened
try:
    attempted = 1
except Exception as error:
    handled = error
finally:
    finished = True
"""
    assert bindings(source) == {
        "conditional", "alternative", "first", "second", "loop",
        "opened", "context", "attempted", "error", "handled", "finished",
    }


def test_local_scopes():
    source = """
def function(parameter):
    local = parameter
    global function_global
    function_global = 1
    return lambda: (lambda_local := 1)
async def asynchronous(parameter):
    async_local = parameter
class Example:
    attribute = 1
    global class_global
    class_global = 2
    def method(self):
        method_local = 3
anonymous = lambda: (lambda_local := 1)
"""
    assert bindings(source) == {"function", "asynchronous", "Example", "anonymous"}


def test_definition_expressions():
    source = """
@(decorator := identity)
def function(argument: (annotation := int) = (default := 1),
             *, option=(keyword_default := 2)) -> (result_type := int):
    pass
@(class_decorator := identity)
class Example((base := object), metaclass=(meta := type)):
    pass
anonymous = lambda argument=(lambda_default := 1): argument
"""
    assert bindings(source) == {
        "decorator", "function", "annotation", "default", "keyword_default",
        "result_type", "class_decorator", "Example", "base", "meta",
        "anonymous", "lambda_default",
    }


def test_comprehensions():
    source = """
values = [(captured := item) for item in source if (accepted := item)]
mapping = {(key := item): (value := item) for item in source}
unique = {(last := item) for item in source}
generator = ((deferred := item) for item in source)
nested = [[(outer := inner) for inner in group] for group in source]
functions = [lambda: (local := item) for item in source]
"""
    assert bindings(source) == {
        "values", "captured", "accepted", "mapping", "key", "value",
        "unique", "last", "generator", "deferred", "nested", "outer",
        "functions",
    }


def test_patterns():
    source = """
match value:
    case {"key": item, **rest}:
        mapping = item
    case [first, *tail]:
        sequence = first
    case Example(attribute=captured) as whole:
        matched = whole
"""
    assert bindings(source) == {
        "item", "rest", "mapping", "first", "tail", "sequence",
        "captured", "whole", "matched",
    }


if __name__ == "__main__":
    test_assignments_and_imports()
    test_control_flow()
    test_local_scopes()
    test_definition_expressions()
    test_comprehensions()
    test_patterns()
