from __future__ import absolute_import
__all__ = ['parent', 'reference', 'refobject']

import gc
import sys

from .dill import _proxy_helper as reference
from .dill import _locate_object as refobject

def parent(obj, objtype, *args, **kwds):
    """
>>> listiter = iter([4,5,6,7])
>>> obj = parent(listiter, list)
>>> obj == [4,5,6,7]  # actually 'is', but don't have handle any longer
True

WARNING: if obj is a sequence (e.g. list), may produce unexpected results.
Parent finds *one* parent (e.g. the last member of the sequence).
    """
    edge_func = gc.get_referents #MMM: looking for refs, not back_refs
    predicate = lambda x: isinstance(x, objtype) #MMM: looking for parent type
    depth = 1 #MMM: always looking for the parent (only, right?)
    chain = find_chain(obj, predicate, edge_func, depth, *args, **kwds)[::-1]
    parent = chain.pop()
    if parent is obj:
        return None
    return parent


# more generic helper function (cut-n-paste from objgraph)
# Source at http://mg.pov.lt/objgraph/
# Copyright (c) 2008-2010 Marius Gedminas <marius@pov.lt>
# Copyright (c) 2010 Stefano Rivera <stefano@rivera.za.net>
# Released under the MIT licence (see objgraph/objgrah.py)

def find_chain(obj, predicate, edge_func, max_depth=20, extra_ignore=()):
    queue = [obj]
    depth = {id(obj): 0}
    parent = {id(obj): None}
    ignore = set(extra_ignore)
    ignore.add(id(extra_ignore))
    ignore.add(id(queue))
    ignore.add(id(depth))
    ignore.add(id(parent))
    ignore.add(id(ignore))
    ignore.add(id(sys._getframe()))  # this function
    ignore.add(id(sys._getframe(1))) # find_chain/find_backref_chain, likely
    gc.collect()
    while queue:
        target = queue.pop(0)
        if predicate(target):
            chain = [target]
            while parent[id(target)] is not None:
                target = parent[id(target)]
                chain.append(target)
            return chain
        tdepth = depth[id(target)]
        if tdepth < max_depth:
            referrers = edge_func(target)
            ignore.add(id(referrers))
            for source in referrers:
                if id(source) in ignore:
                    continue
                if id(source) not in depth:
                    depth[id(source)] = tdepth + 1
                    parent[id(source)] = target
                    queue.append(source)
    return [obj] # not found

