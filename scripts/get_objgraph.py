#!/usr/bin/env python
"""
use objgraph to plot the reference paths for types found in dill.detect.types
"""
#XXX: useful if could read .pkl file and generate the graph... ?

import dill as pickle
#pickle.debug.trace(True)
#import pickle

# get all objects for testing
from dill.detect import load_types
load_types(pickleable=True,unpickleable=True)
from dill.detect import objects

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print "Please provide exactly one type name (e.g. 'IntType')"
        print "\n",
        for objtype in objects.keys()[:40]:
            print objtype,
        print "..."
    else:
        objtype = str(sys.argv[-1])
        obj = objects[objtype]
        try:
            import objgraph
            objgraph.show_refs(obj, filename=objtype+'.png')
        except ImportError:
            print "Please install 'objgraph' to view object graphs"


# EOF
