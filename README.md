dill
====
serialize all of python

About Dill
----------
Dill extends python's 'pickle' module for serializing and de-serializing
python objects to the majority of the built-in python types. Serialization
is the process of converting an object to a byte stream, and the inverse
of which is converting a byte stream back to on python object hierarchy.

Dill provides the user the same interface as the 'pickle' module, and
also includes some additional features. In addition to pickling python
objects, dill provides the ability to save the state of an interpreter
session in a single command.  Hence, it would be feasable to save a
interpreter session, close the interpreter, ship the pickled file to
another computer, open a new interpreter, unpickle the session and
thus continue from the 'saved' state of the original interpreter
session.

Dill can be used to store python objects to a file, but the primary
usage is to send python objects across the network as a byte stream.
Dill is quite flexible, and allows arbitrary user defined classes
and funcitons to be serialized.  Thus dill is not intended to be
secure against erroneously or maliciously constructed data. It is
left to the user to decide whether the data they unpickle is from
a trustworthy source.

Dill is part of pathos, a python framework for heterogenous computing.
Dill is in the early development stages, and any user feedback is
highly appreciated. Contact Mike McKerns [mmckerns at caltech dot edu] with
comments, suggestions, and any bugs you may find. A list of known issues
is maintained at http://trac.mystic.cacr.caltech.edu/project/pathos/query.


Major Features
--------------
Dill can pickle the following standard types::

* none, type, bool, int, long, float, complex, str, unicode,
* tuple, list, dict, file, buffer, builtin,
* both old and new style classes,
* instances of old and new style classes,
* set, frozenset, array, functions, exceptions

Dill can also pickle more 'exotic' standard types::

* functions with yields, nested functions, lambdas
* cell, method, unboundmethod, module, code, methodwrapper,
* dictproxy, methoddescriptor, getsetdescriptor, memberdescriptor,
* wrapperdescriptor, xrange, slice,
* notimplemented, ellipsis, quit

Dill cannot yet pickle these standard types::

* frame, generator, traceback

Dill also provides the capability to::

* save and load python interpreter sessions
* save and extract the source code from functions and classes
* interactively diagnose pickling errors

Current Release
---------------
The latest released version of dill is available from::
    http://dev.danse.us/trac/pathos

Dill is distributed under a modified BSD license.

Development Release
-------------------
You can get the latest development release with all the shiny new features at::
    http://dev.danse.us/packages.

or even better, fork us on our github mirror of the svn trunk::
    https://github.com/uqfoundation

Citation
--------
If you use dill to do research that leads to publication, we ask that you
acknowledge use of dill by citing the following in your publication::

    M.M. McKerns, L. Strand, T. Sullivan, A. Fang, M.A.G. Aivazis,
    "Building a framework for predictive science", Proceedings of
    the 10th Python in Science Conference, 2011;
    http://arxiv.org/pdf/1202.1056

    Michael McKerns and Michael Aivazis,
    "pathos: a framework for heterogeneous computing", 2010- ;
    http://dev.danse.us/trac/pathos

More Information
----------------
Probably the best way to get started is to look at the tests
that are provide within dill. See `dill.tests` for a set of scripts
that test dill's ability to serialize different python objects.
Since dill conforms to the 'pickle' interface, the examples and
documentation at http://docs.python.org/library/pickle.html also
apply to dill if one will `import dill as pickle`. Dill's source code is also generally well documented,
so further questions may be resolved by inspecting the code itself, or through 
browsing the reference manual. For those who like to leap before
they look, you can jump right to the installation instructions. If the aforementioned documents do not adequately address your needs, please send us feedback.

Dill is an active research tool. There are a growing number of publications and presentations that
discuss real-world examples and new features of dill in greater detail than presented in the user's guide. 
If you would like to share how you use dill in your work, please send us a link.
