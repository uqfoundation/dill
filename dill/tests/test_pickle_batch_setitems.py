import io

import dill._dill as _dill


def test_batch_setitems_legacy_override_signature():
    buffer = io.BytesIO()
    captured = []

    class LegacyPickler(_dill.Pickler):
        def _batch_setitems(self, items):
            captured.append(list(items))

    pickler = LegacyPickler(buffer)
    _dill._call_batch_setitems(pickler, iter({"a": 1}.items()), obj={"sentinel": True})

    assert captured == [[("a", 1)]]


def test_batch_setitems_obj_forwarded():
    buffer = io.BytesIO()
    observed = []

    class ModernPickler(_dill.Pickler):
        def _batch_setitems(self, items, obj=None):
            items_list = list(items)
            observed.append(obj)
            super()._batch_setitems(iter(items_list), obj=obj)

    pickler = ModernPickler(buffer)
    marker = {"sentinel": True}
    _dill._call_batch_setitems(pickler, iter({"a": 1}.items()), obj=marker)

    assert observed == [marker]
