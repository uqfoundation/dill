dill module documentation
=========================

detect module
-------------

.. automodule:: dill.detect
..  :exclude-members: +ismethod, isfunction, istraceback, isframe, iscode, parent, reference, at, parents, children

logger module
-------------

.. automodule:: dill.logger
    :exclude-members: +trace

objtypes module
---------------

.. automodule:: dill.objtypes
..  :exclude-members: +

pointers module
---------------

.. automodule:: dill.pointers
..  :exclude-members: +

session module
--------------

.. automodule:: dill.session
..  :exclude-members: +dump_session, load_session

settings module
---------------

.. automodule:: dill.settings
..  :exclude-members: +

source module
-------------

``source.importable`` can recreate a function and its dependencies as Python
source. When those dependencies introduce extra names, executing the source
exports only the function's name (or the requested alias). For example::

    from dill.source import importable

    def factory(offset):
        def add_offset(value):
            return value + offset
        return add_offset

    namespace = {}
    exec(importable(factory(1), alias='add_one', source=True), namespace)
    exec(importable(factory(10), alias='add_ten', source=True), namespace)
    assert namespace['add_one'](0) == 1
    assert namespace['add_ten'](0) == 10
    assert 'offset' not in namespace
    assert 'add_offset' not in namespace

Functions and methods that require extra bindings are constructed in a private
namespace. Dependencies within one export share that namespace, and separate
exports do not overwrite each other's captured values. The destination's
``__name__``, ``__package__``, and ``__builtins__`` are retained. Other destination
bindings are not copied into the private namespace.

Plain definitions and import statements remain direct source. Classes and
instances retain their existing source behavior. The private execution uses
``'<string>'`` as its filename; to inspect an isolated function's source again,
keep the original object or the string returned by ``importable``.

.. automodule:: dill.source
..  :exclude-members: +

temp module
-----------

.. automodule:: dill.temp
..  :exclude-members: +
