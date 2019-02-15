# This module is used by the `test_shadowed_namedtuple` test.
# Author: Sergei Fomin (se4min at yandex-team.ru)

from collections import namedtuple

class Shadowed(namedtuple("Shadowed", [])):
    pass

def shadowed():
    return Shadowed()

