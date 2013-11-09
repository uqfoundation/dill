import dill

class _class:
    def _method(self):
        pass
    def ok(self):
        return True

class _class2:
    def __call__(self):
        pass
    def ok(self):
        return True

class _newclass(object):
    def _method(self):
        pass
    def ok(self):
        return True

class _newclass2(object):
    def __call__(self):
        pass
    def ok(self):
        return True

o = _class()
oc = _class2()
n = _newclass()
nc = _newclass2()

clslist = [_class,_class2,_newclass,_newclass2]
objlist = [o,oc,n,nc]
_clslist = [dill.dumps(obj) for obj in clslist]
_objlist = [dill.dumps(obj) for obj in objlist]

for obj in clslist:
    globals().pop(obj.__name__)
del clslist
for obj in ['o','oc','n','nc']:
    globals().pop(obj)
del objlist
del obj

for obj,cls in zip(_objlist,_clslist):
    _cls = dill.loads(cls)
    _obj = dill.loads(obj)
    assert _obj.ok()
    assert _cls.ok(_cls())


# EOF
