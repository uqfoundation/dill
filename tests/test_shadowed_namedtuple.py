#!/usr/bin/env python
#
# Author: Sergei Fomin (se4min at yandex-team.ru)

from dill import dumps, loads
from shadowed_namedtuple import shadowed

def test_shadowed_namedtuple():
    obj = shadowed()
    obj_loaded = loads(dumps(obj))
    assert obj.__class__ is obj_loaded.__class__

if __name__ == "__main__":
    test_shadowed_namedtuple()

