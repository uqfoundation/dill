try:
    import enum
    from enum import Enum, IntEnum, EnumMeta, Flag, IntFlag, unique, auto
except:
    Enum = None

import abc

import dill
import sys

dill.settings['recurse'] = True

"""
Test cases copied from https://raw.githubusercontent.com/python/cpython/3.10/Lib/test/test_enum.py

Copyright 1991-1995 by Stichting Mathematisch Centrum, Amsterdam, The Netherlands.

All Rights Reserved
Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee is hereby granted, provided that
the above copyright notice appear in all copies and that both that copyright
notice and this permission notice appear in supporting documentation, and that
the names of Stichting Mathematisch Centrum or CWI or Corporation for National
Research Initiatives or CNRI not be used in advertising or publicity pertaining
to distribution of the software without specific, written prior permission.

While CWI is the initial source for this software, a modified version is made
available by the Corporation for National Research Initiatives (CNRI) at the
Internet address http://www.python.org.

STICHTING MATHEMATISCH CENTRUM AND CNRI DISCLAIM ALL WARRANTIES WITH REGARD TO
THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS,
IN NO EVENT SHALL STICHTING MATHEMATISCH CENTRUM OR CNRI BE LIABLE FOR ANY
SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING
FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""

def test_enums():

    class Stooges(Enum):
        LARRY = 1
        CURLY = 2
        MOE = 3

    class IntStooges(int, Enum):
        LARRY = 1
        CURLY = 2
        MOE = 3

    class FloatStooges(float, Enum):
        LARRY = 1.39
        CURLY = 2.72
        MOE = 3.142596

    class FlagStooges(Flag):
        LARRY = 1
        CURLY = 2
        MOE = 3

    # https://stackoverflow.com/a/56135108
    class ABCEnumMeta(abc.ABCMeta, EnumMeta):
        def __new__(mcls, *args, **kw):
            abstract_enum_cls = super().__new__(mcls, *args, **kw)
            # Only check abstractions if members were defined.
            if abstract_enum_cls._member_map_:
                try:  # Handle existence of undefined abstract methods.
                    absmethods = list(abstract_enum_cls.__abstractmethods__)
                    if absmethods:
                        missing = ', '.join(f'{method!r}' for method in absmethods)
                        plural = 's' if len(absmethods) > 1 else ''
                        raise TypeError(
                           f"cannot instantiate abstract class {abstract_enum_cls.__name__!r}"
                           f" with abstract method{plural} {missing}")
                except AttributeError:
                    pass
            return abstract_enum_cls

    if dill._dill.PY3:
        l = locals()
        exec("""class StrEnum(str, abc.ABC, Enum, metaclass=ABCEnumMeta):
            'accepts only string values'
            def invisible(self):
                return "did you see me?" """, None, l)
        StrEnum = l['StrEnum']
    else:
        class StrEnum(str, abc.ABC, Enum):
            __metaclass__ = ABCEnumMeta
            'accepts only string values'
            def invisible(self):
                return "did you see me?"

    class Name(StrEnum):
        BDFL = 'Guido van Rossum'
        FLUFL = 'Barry Warsaw'

    assert 'invisible' in dir(dill.copy(Name).BDFL)
    assert 'invisible' in dir(dill.copy(Name.BDFL))
    assert dill.copy(Name.BDFL) is not Name.BDFL

    Question = Enum('Question', 'who what when where why', module=__name__)
    Answer = Enum('Answer', 'him this then there because')
    Theory = Enum('Theory', 'rule law supposition', qualname='spanish_inquisition')

    class Fruit(Enum):
        TOMATO = 1
        BANANA = 2
        CHERRY = 3

    assert dill.copy(Fruit).TOMATO.value == 1 and dill.copy(Fruit).TOMATO != 1 \
        and dill.copy(Fruit).TOMATO is not Fruit.TOMATO

    from datetime import date
    class Holiday(date, Enum):
        NEW_YEAR = 2013, 1, 1
        IDES_OF_MARCH = 2013, 3, 15

    assert hasattr(dill.copy(Holiday), 'NEW_YEAR')

    class HolidayTuple(tuple, Enum):
        NEW_YEAR = 2013, 1, 1
        IDES_OF_MARCH = 2013, 3, 15

    assert isinstance(dill.copy(HolidayTuple).NEW_YEAR, tuple)

    class SuperEnum(IntEnum):
        def __new__(cls, value, description=""):
            obj = int.__new__(cls, value)
            obj._value_ = value
            obj.description = description
            return obj

    class SubEnum(SuperEnum):
        sample = 5

    if sys.hexversion >= 0x030a0000:
        assert 'description' in dir(dill.copy(SubEnum.sample))
        assert 'description' in dir(dill.copy(SubEnum).sample)

    class WeekDay(IntEnum):
        SUNDAY = 1
        MONDAY = 2
        TUESDAY = TEUSDAY = 3
        WEDNESDAY = 4
        THURSDAY = 5
        FRIDAY = 6
        SATURDAY = 7

    WeekDay_ = dill.copy(WeekDay)
    assert WeekDay_.TUESDAY is WeekDay_.TEUSDAY

    class AutoNumber(IntEnum):
        def __new__(cls):
            value = len(cls.__members__) + 1
            obj = int.__new__(cls, value)
            obj._value_ = value
            return obj

    class Color(AutoNumber):
        red = ()
        green = ()
        blue = ()

    # TODO: This doesn't work yet
    # Color_ = dill.copy(Color)
    # assert list(Color_) == [Color_.red, Color_.green, Color_.blue]
    # assert list(map(int, Color_)) == [1, 2, 3]

if __name__ == '__main__':
    test_enums()
