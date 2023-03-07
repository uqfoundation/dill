# Copyright (c) 2015 CensoredUsername

# This module provides tools for safely analyizing pickle files programmatically

import sys

PY3 = sys.version_info >= (3, 0)
PY2 = not PY3

import types
import pickle
import struct

if PY3:
    from io import BytesIO as StringIO
else:
    from cStringIO import StringIO

__all__ = [
    "load", "loads", "safe_load", "safe_loads", "safe_dump", "safe_dumps",
    "fake_package", "remove_fake_package",
    "FakeModule", "FakePackage", "FakePackageLoader",
    "FakeClassType", "FakeClassFactory",
    "FakeClass", "FakeStrict", "FakeWarning", "FakeIgnore",
    "FakeUnpicklingError", "FakeUnpickler", "SafeUnpickler",
    "SafePickler"
]

# Fake class implementation

class FakeClassType(type):
    """
    The metaclass used to create fake classes. To support comparisons between
    fake classes and :class:`FakeModule` instances custom behaviour is defined
    here which follows this logic:

    If the other object does not have ``other.__name__`` set, they are not equal.

    Else if it does not have ``other.__module__`` set, they are equal if
    ``self.__module__ + "." + self.__name__ == other.__name__``.

    Else, they are equal if
    ``self.__module__ == other.__module__ and self.__name__ == other.__name__``

    Using this behaviour, ``==``, ``!=``, ``hash()``, ``isinstance()`` and ``issubclass()``
    are implemented allowing comparison between :class:`FakeClassType` instances
    and :class:`FakeModule` instances to succeed if they are pretending to be in the same
    place in the python module hierarchy.

    To create a fake class using this metaclass, you can either use this metaclass directly or
    inherit from the fake class base instances given below. When doing this, the module that
    this fake class is pretending to be in should be specified using the *module* argument
    when the metaclass is called directly or a :attr:``__module__`` class attribute in a class statement.

    This is a subclass of :class:`type`.
    """

    # instance creation logic

    def __new__(cls, name, bases, attributes, module=None):
        # This would be a lie
        attributes.pop("__qualname__", None)

        # figure out what module we should say we're in
        # note that if no module is explicitly passed, the current module will be chosen
        # due to the class statement implicitly specifying __module__ as __name__
        if module is not None:
            attributes["__module__"] = module

        if "__module__" not in attributes:
            raise TypeError("No module has been specified for FakeClassType {0}".format(name))

        # assemble instance
        return type.__new__(cls, name, bases, attributes)

    def __init__(self, name, bases, attributes, module=None):
        type.__init__(self, name, bases, attributes)

    # comparison logic

    def __eq__(self, other):
        if not hasattr(other, "__name__"):
            return False
        if hasattr(other, "__module__"):
            return self.__module__ == other.__module__ and self.__name__ == other.__name__
        else:
            return self.__module__ + "." + self.__name__ == other.__name__

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.__module__ + "." + self.__name__)

    def __instancecheck__(self, instance):
        return self.__subclasscheck__(instance.__class__)

    def __subclasscheck__(self, subclass):
        return (self == subclass or
                (bool(subclass.__bases__) and
                 any(self.__subclasscheck__(base) for base in subclass.__bases__)))

# PY2 doesn't like the PY3 way of metaclasses and PY3 doesn't support the PY2 way
# so we call the metaclass directly
FakeClass = FakeClassType("FakeClass", (), {"__doc__": """
A barebones instance of :class:`FakeClassType`. Inherit from this to create fake classes.
"""}, module=__name__)

class FakeStrict(FakeClass, object):
    def __new__(cls, *args, **kwargs):
        self = FakeClass.__new__(cls)
        if args or kwargs:
            raise FakeUnpicklingError("{0} was instantiated with unexpected arguments {1}, {2}".format(cls, args, kwargs))
        return self

    def __setstate__(self, state):
        slotstate = None

        if (isinstance(state, tuple) and len(state) == 2 and
            (state[0] is None or isinstance(state[0], dict)) and
            (state[1] is None or isinstance(state[1], dict))):
            state, slotstate = state

        if state:
            # Don't have to check for slotstate here since it's either None or a dict
            if not isinstance(state, dict):
                raise FakeUnpicklingError("{0}.__setstate__() got unexpected arguments {1}".format(self.__class__, state))
            else:
                self.__dict__.update(state)

        if slotstate:
            self.__dict__.update(slotstate)

class FakeWarning(FakeClass, object):
    def __new__(cls, *args, **kwargs):
        self = FakeClass.__new__(cls)
        if args or kwargs:
            print("{0} was instantiated with unexpected arguments {1}, {2}".format(cls, args, kwargs))
            self._new_args = args
        return self

    def __setstate__(self, state):
        slotstate = None

        if (isinstance(state, tuple) and len(state) == 2 and
            (state[0] is None or isinstance(state[0], dict)) and
            (state[1] is None or isinstance(state[1], dict))):
            state, slotstate = state

        if state:
            # Don't have to check for slotstate here since it's either None or a dict
            if not isinstance(state, dict):
                print("{0}.__setstate__() got unexpected arguments {1}".format(self.__class__, state))
                self._setstate_args = state
            else:
                self.__dict__.update(state)

        if slotstate:
            self.__dict__.update(slotstate)

class FakeIgnore(FakeClass, object):
    def __new__(cls, *args, **kwargs):
        self = FakeClass.__new__(cls)
        if args:
            self._new_args = args
        if kwargs:
            self._new_kwargs = kwargs
        return self

    def __setstate__(self, state):
        slotstate = None

        if (isinstance(state, tuple) and len(state) == 2 and
            (state[0] is None or isinstance(state[0], dict)) and
            (state[1] is None or isinstance(state[1], dict))):
            state, slotstate = state

        if state:
            # Don't have to check for slotstate here since it's either None or a dict
            if not isinstance(state, dict):
                self._setstate_args = state
            else:
                self.__dict__.update(state)

        if slotstate:
            self.__dict__.update(slotstate)

class FakeClassFactory(object):
    """
    Factory of fake classses. It will create fake class definitions on demand
    based on the passed arguments.
    """

    def __init__(self, special_cases=(), default_class=FakeStrict):
        """
        *special_cases* should be an iterable containing fake classes which should be treated
        as special cases during the fake unpickling process. This way you can specify custom methods
        and attributes on these classes as they're used during unpickling.

        *default_class* should be a FakeClassType instance which will be subclassed to create the
        necessary non-special case fake classes during unpickling. This should usually be set to
        :class:`FakeStrict`, :class:`FakeWarning` or :class:`FakeIgnore`. These classes have
        :meth:`__new__` and :meth:`__setstate__` methods which extract data from the pickle stream
        and provide means of inspecting the stream when it is not clear how the data should be interpreted.

        As an example, we can define the fake class generated for definition bar in module foo,
        which has a :meth:`__str__` method which returns ``"baz"``::

           class bar(FakeStrict, object):
               def __str__(self):
                   return "baz"

           special_cases = [bar]

        Alternatively they can also be instantiated using :class:`FakeClassType` directly::
           special_cases = [FakeClassType(c.__name__, c.__bases__, c.__dict__, c.__module__)]
        """
        self.special_cases = dict(((i.__module__, i.__name__), i) for i in special_cases)
        self.default = default_class

        self.class_cache = {}

    def __call__(self, name, module):
        """
        Return the right class for the specified *module* and *name*.

        This class will either be one of the special cases in case the name and module match,
        or a subclass of *default_class* will be created with the correct name and module.

        Created class definitions are cached per factory instance.
        """
        # Check if we've got this class cached
        klass = self.class_cache.get((module, name), None)
        if klass is not None:
            return klass

        klass = self.special_cases.get((module, name), None)

        if not klass:
            # generate a new class def which inherits from the default fake class
            klass = type(name, (self.default,), {"__module__": module})

        self.class_cache[(module, name)] = klass
        return klass

# Fake module implementation

class FakeModule(types.ModuleType):
    """
    An object which pretends to be a module.

    *name* is the name of the module and should be a ``"."`` separated
    alphanumeric string.

    On initialization the module is added to sys.modules so it can be
    imported properly. Further if *name* is a submodule and if its parent
    does not exist, it will automatically create a parent :class:`FakeModule`.
    This operates recursively until the parent is a top-level module or
    when the parent is an existing module.

    If any fake submodules are removed from this module they will
    automatically be removed from :data:`sys.modules`.

    Just as :class:`FakeClassType`, it supports comparison with
    :class:`FakeClassType` instances, using the following logic:

    If the object does not have ``other.__name__`` set, they are not equal.

    Else if the other object does not have ``other.__module__`` set, they are equal if:
    ``self.__name__ == other.__name__``

    Else, they are equal if:
    ``self.__name__ == other.__module__ + "." + other.__name__``

    Using this behaviour, ``==``, ``!=``, ``hash()``, ``isinstance()`` and ``issubclass()``
    are implemented allowing comparison between :class:`FakeClassType` instances
    and :class:`FakeModule` instances to succeed if they are pretending to bein the same
    place in the python module hierarchy.

    It inherits from :class:`types.ModuleType`.
    """
    def __init__(self, name):
        super(FakeModule, self).__init__(name)
        sys.modules[name] = self

        if "." in name:
            parent_name, child_name = name.rsplit(".", 1)

            try:
                __import__(parent_name)
                parent = sys.modules[parent_name]
            except:
                parent = FakeModule(parent_name)
            setattr(parent, child_name, self)

    def __repr__(self):
        return "<module '{0}' (fake)>".format(self.__name__)

    def __str__(self):
        return self.__repr__()

    def __setattr__(self, name, value):
        # If a fakemodule is removed we need to remove its entry from sys.modules
        if (name in self.__dict__ and
            isinstance(self.__dict__[name], FakeModule) and not
            isinstance(value, FakeModule)):

            self.__dict__[name]._remove()
        self.__dict__[name] = value

    def __delattr__(self, name):
        if isinstance(self.__dict__[name], FakeModule):
            self.__dict__[name]._remove()
        del self.__dict__[name]

    def _remove(self):
        """
        Removes this module from :data:`sys.modules` and calls :meth:`_remove` on any
        sub-FakeModules.
        """
        for i in tuple(self.__dict__.keys()):
            if isinstance(self.__dict__[i], FakeModule):
                self.__dict__[i]._remove()
                del self.__dict__[i]
        del sys.modules[self.__name__]

    def __eq__(self, other):
        if not hasattr(other, "__name__"):
            return False
        othername = other.__name__
        if hasattr(other, "__module__"):
            othername = other.__module__ + "." + other.__name__

        return self.__name__ == othername

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.__name__)

    def __instancecheck__(self, instance):
        return self.__subclasscheck__(instance.__class__)

    def __subclasscheck__(self, subclass):
        return (self == subclass or
                (bool(subclass.__bases__) and
                 any(self.__subclasscheck__(base) for base in subclass.__bases__)))

class FakePackage(FakeModule):
    """
    A :class:`FakeModule` subclass which lazily creates :class:`FakePackage`
    instances on its attributes when they're requested.

    This ensures that any attribute of this module is a valid FakeModule
    which can be used to compare against fake classes.
    """
    __path__ = []

    def __call__(self, *args, **kwargs):
        # This mainly exists to print a nicer error message when
        # someone tries to call a FakePackage instance
        raise TypeError("'{0}' FakePackage object is not callable".format(self.__name__))

    def __getattr__(self, name):
        modname = self.__name__ + "." + name
        mod = sys.modules.get(modname, None)
        if mod is None:
            try:
                __import__(modname)
            except:
                mod = FakePackage(modname)
            else:
                mod = sys.modules[modname]
        return mod

class FakePackageLoader(object):
    """
    A :term:`loader` of :class:`FakePackage` modules. When added to
    :data:`sys.meta_path` it will ensure that any attempt to import
    module *root* or its submodules results in a FakePackage.

    Together with the attribute creation from :class:`FakePackage`
    this ensures that any attempt to get a submodule from module *root*
    results in a FakePackage, creating the illusion that *root* is an
    actual package tree.
    """
    def __init__(self, root):
        self.root = root

    def find_module(self, fullname, path=None):
        if fullname == self.root or fullname.startswith(self.root + "."):
            return self
        else:
            return None

    def load_module(self, fullname):
        return FakePackage(fullname)

# Fake unpickler implementation

class FakeUnpicklingError(pickle.UnpicklingError):
    """
    Error raised when there is not enough information to perform the fake
    unpickling process completely. It inherits from :exc:`pickle.UnpicklingError`.
    """
    pass

class FakeUnpickler(pickle.Unpickler if PY2 else pickle._Unpickler):
    """
    A forgiving unpickler. On uncountering references to class definitions
    in the pickle stream which it cannot locate, it will create fake classes
    and if necessary fake modules to house them in. Since it still allows access
    to all modules and builtins, it should only be used to unpickle trusted data.

    *file* is the :term:`binary file` to unserialize.

    The optional keyword arguments are *class_factory*, *encoding and *errors*.
    *class_factory* can be used to control how the missing class definitions are
    created. If set to ``None``, ``FakeClassFactory((), FakeStrict)`` will be used.

    In Python 3, the optional keyword arguments *encoding* and *errors* can be used
    to indicate how the unpickler should deal with pickle streams generated in python
    2, specifically how to deal with 8-bit string instances. If set to "bytes" it will
    load them as bytes objects, otherwise it will attempt to decode them into unicode
    using the given *encoding* and *errors* arguments.

    It inherits from :class:`pickle.Unpickler`. (In Python 3 this is actually
    ``pickle._Unpickler``)
    """
    if PY2:
        def __init__(self, file, class_factory=None, encoding="bytes", errors="strict"):
            pickle.Unpickler.__init__(self, file,)
            self.class_factory = class_factory or FakeClassFactory()
    else:
        def __init__(self, file, class_factory=None, encoding="bytes", errors="strict"):
            super().__init__(file, fix_imports=False, encoding=encoding, errors=errors)
            self.class_factory = class_factory or FakeClassFactory()

    def find_class(self, module, name):
        mod = sys.modules.get(module, None)
        if mod is None:
            try:
                __import__(module)
            except:
                mod = FakeModule(module)
            else:
                mod = sys.modules[module]

        klass = getattr(mod, name, None)
        if klass is None or isinstance(klass, FakeModule):
            klass = self.class_factory(name, module)
            setattr(mod, name, klass)

        return klass

class SafeUnpickler(FakeUnpickler):
    """
    A safe unpickler. It will create fake classes for any references to class
    definitions in the pickle stream. Further it can block access to the extension
    registry making this unpickler safe to use on untrusted data.

    *file* is the :term:`binary file` to unserialize.

    The optional keyword arguments are *class_factory*, *safe_modules*, *use_copyreg*,
    *encoding* and *errors*. *class_factory* can be used to control how the missing class
    definitions are created. If set to ``None``, ``FakeClassFactory((), FakeStrict)`` will be
    used. *safe_modules* can be set to a set of strings of module names, which will be
    regarded as safe by the unpickling process, meaning that it will import objects
    from that module instead of generating fake classes (this does not apply to objects
    in submodules). *use_copyreg* is a boolean value indicating if it's allowed to
    use extensions from the pickle extension registry (documented in the :mod:`copyreg`
    module).

    In Python 3, the optional keyword arguments *encoding* and *errors* can be used
    to indicate how the unpickler should deal with pickle streams generated in python
    2, specifically how to deal with 8-bit string instances. If set to "bytes" it will
    load them as bytes objects, otherwise it will attempt to decode them into unicode
    using the given *encoding* and *errors* arguments.

    This function can be used to unpickle untrusted data safely with the default
    class_factory when *safe_modules* is empty and *use_copyreg* is False.
    It inherits from :class:`pickle.Unpickler`. (In Python 3 this is actually
    ``pickle._Unpickler``)

    It should be noted though that when the unpickler tries to get a nonexistent
    attribute of a safe module, an :exc:`AttributeError` will be raised.

    This inherits from :class:`FakeUnpickler`
    """
    def __init__(self, file, class_factory=None, safe_modules=(),
                 use_copyreg=False, encoding="bytes", errors="strict"):
        FakeUnpickler.__init__(self, file, class_factory, encoding=encoding, errors=errors)
        # A set of modules which are safe to load
        self.safe_modules = set(safe_modules)
        self.use_copyreg = use_copyreg

    def find_class(self, module, name):
        if module in self.safe_modules:
            __import__(module)
            mod = sys.modules[module]
            if not hasattr(mod, "__all__") or name in mod.__all__:
                klass = getattr(mod, name)
                return klass

        return self.class_factory(name, module)

    def get_extension(self, code):
        if self.use_copyreg:
            return FakeUnpickler.get_extension(self, code)
        else:
            return self.class_factory("extension_code_{0}".format(code), "copyreg")

class SafePickler(pickle.Pickler if PY2 else pickle._Pickler):
    """
    A pickler which can repickle object hierarchies containing objects created by SafeUnpickler.
    Due to reasons unknown, pythons pickle implementation will normally check if a given class
    actually matches with the object specified at the __module__ and __name__ of the class. Since
    this check is performed with object identity instead of object equality we cannot fake this from
    the classes themselves, and we need to override the method used for normally saving classes.
    """

    def save_global(self, obj, name=None, pack=struct.pack):
        if isinstance(obj, FakeClassType):
            self.write(pickle.GLOBAL + obj.__module__ + '\n' + obj.__name__ + '\n')
            self.memoize(obj)
            return

        pickle.Pickler.save_global(self, obj, name, pack)

# the main API

def load(file, class_factory=None, encoding="bytes", errors="errors"):
    """
    Read a pickled object representation from the open binary :term:`file object` *file*
    and return the reconstitutded object hierarchy specified therein, generating
    any missing class definitions at runtime. This is equivalent to
    ``FakeUnpickler(file).load()``.

    The optional keyword arguments are *class_factory*, *encoding* and *errors*.
    *class_factory* can be used to control how the missing class definitions are
    created. If set to ``None``, ``FakeClassFactory({}, 'strict')`` will be used.

    In Python 3, the optional keyword arguments *encoding* and *errors* can be used
    to indicate how the unpickler should deal with pickle streams generated in python
    2, specifically how to deal with 8-bit string instances. If set to "bytes" it will
    load them as bytes objects, otherwise it will attempt to decode them into unicode
    using the given *encoding* and *errors* arguments.

    This function should only be used to unpickle trusted data.
    """
    return FakeUnpickler(file, class_factory, encoding=encoding, errors=errors).load()

def loads(string, class_factory=None, encoding="bytes", errors="errors"):
    """
    Simjilar to :func:`load`, but takes an 8-bit string (bytes in Python 3, str in Python 2)
    as its first argument instead of a binary :term:`file object`.
    """
    return FakeUnpickler(StringIO(string), class_factory,
                         encoding=encoding, errors=errors).load()

def safe_load(file, class_factory=None, safe_modules=(), use_copyreg=False,
              encoding="bytes", errors="errors"):
    """
    Read a pickled object representation from the open binary :term:`file object` *file*
    and return the reconstitutded object hierarchy specified therein, substituting any
    class definitions by fake classes, ensuring safety in the unpickling process.
    This is equivalent to ``SafeUnpickler(file).load()``.

    The optional keyword arguments are *class_factory*, *safe_modules*, *use_copyreg*,
    *encoding* and *errors*. *class_factory* can be used to control how the missing class
    definitions are created. If set to ``None``, ``FakeClassFactory({}, 'strict')`` will be
    used. *safe_modules* can be set to a set of strings of module names, which will be
    regarded as safe by the unpickling process, meaning that it will import objects
    from that module instead of generating fake classes (this does not apply to objects
    in submodules). *use_copyreg* is a boolean value indicating if it's allowed to
    use extensions from the pickle extension registry (documented in the :mod:`copyreg`
    module).

    In Python 3, the optional keyword arguments *encoding* and *errors* can be used
    to indicate how the unpickler should deal with pickle streams generated in python
    2, specifically how to deal with 8-bit string instances. If set to "bytes" it will
    load them as bytes objects, otherwise it will attempt to decode them into unicode
    using the given *encoding* and *errors* arguments.

    This function can be used to unpickle untrusted data safely with the default
    class_factory when *safe_modules* is empty and *use_copyreg* is False.
    """
    return SafeUnpickler(file, class_factory, safe_modules, use_copyreg,
                         encoding=encoding, errors=errors).load()

def safe_loads(string, class_factory=None, safe_modules=(), use_copyreg=False,
               encoding="bytes", errors="errors"):
    """
    Similar to :func:`safe_load`, but takes an 8-bit string (bytes in Python 3, str in Python 2)
    as its first argument instead of a binary :term:`file object`.
    """
    return SafeUnpickler(StringIO(string), class_factory, safe_modules, use_copyreg,
                         encoding=encoding, errors=errors).load()

def safe_dump(obj, file, protocol=pickle.HIGHEST_PROTOCOL):
    """
    A convenience function wrapping SafePickler. It functions similarly to pickle.dump
    """
    SafePickler(file, protocol).dump(obj)

def safe_dumps(obj, protocol=pickle.HIGHEST_PROTOCOL):
    """
    A convenience function wrapping SafePickler. It functions similarly to pickle.dumps
    """
    file = StringIO()
    SafePickler(file, protocol).dump(obj)
    return file.getvalue()

def fake_package(name):
    """
    Mounts a fake package tree with the name *name*. This causes any attempt to import
    module *name*, attributes of the module or submodules will return a :class:`FakePackage`
    instance which implements the same behaviour. These :class:`FakePackage` instances compare
    properly with :class:`FakeClassType` instances allowing you to code using FakePackages as
    if the modules and their attributes actually existed.

    This is implemented by creating a :class:`FakePackageLoader` instance with root *name*
    and inserting it in the first spot in :data:`sys.meta_path`. This ensures that importing the
    module and submodules will work properly. Further the :class:`FakePackage` instances take
    care of generating submodules as attributes on request.

    If a fake package tree with the same *name* is already registered, no new fake package
    tree will be mounted.

    This returns the :class:`FakePackage` instance *name*.
    """
    if name in sys.modules and isinstance(sys.modules[name], FakePackage):
        return sys.modules[name]
    else:
        loader = FakePackageLoader(name)
        sys.meta_path.insert(0, loader)
        return __import__(name)

def remove_fake_package(name):
    """
    Removes the fake package tree mounted at *name*.

    This works by first looking for any FakePackageLoaders in :data:`sys.path`
    with their root set to *name* and removing them from sys.path. Next it will
    find the top-level :class:`FakePackage` instance *name* and from this point
    traverse the tree of created submodules, removing them from :data:`sys.path`
    and removing their attributes. After this the modules are not registered
    anymore and if they are not referenced from user code anymore they will be
    garbage collected.

    If no fake package tree *name* exists a :exc:`ValueError` will be raised.
    """

    # Get the package entry via its entry in sys.modules
    package = sys.modules.get(name, None)
    if package is None:
        raise ValueError("No fake package with the name {0} found".format(name))

    if not isinstance(package, FakePackage):
        raise ValueError("The module {0} is not a fake package".format(name))

    # Attempt to remove the loader from sys.meta_path

    loaders = [i for i in sys.meta_path if isinstance(i, FakePackageLoader) and i.root == name]
    for loader in loaders:
        sys.meta_path.remove(loader)

    # Remove all module and submodule entries from sys.modules
    package._remove()

    # It is impossible to kill references to the modules, but all traces
    # of it have been removed from the import machinery and the submodule
    # tree structure has been broken up.