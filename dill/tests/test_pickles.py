"""Tests for warning handling in dill.pickles."""

import warnings

import dill


class RaisesOnEquality:
    def __eq__(self, other):
        raise RuntimeError('cannot compare')


class WarnsOnEquality:
    def __eq__(self, other):
        warnings.warn('comparison warning', UserWarning)
        return True


def test_existing_ignore_filter_is_preserved():
    with warnings.catch_warnings():
        warnings.resetwarnings()
        warnings.simplefilter('ignore')
        before = list(warnings.filters)

        assert dill.pickles(42)

        assert warnings.filters == before


def test_warning_filters_are_restored_after_safe_failure():
    with warnings.catch_warnings():
        warnings.resetwarnings()
        warnings.simplefilter('error', UserWarning)
        before = list(warnings.filters)

        assert not dill.pickles(RaisesOnEquality(), safe=True)

        assert warnings.filters == before
        try:
            warnings.warn('still visible', UserWarning)
        except UserWarning:
            pass
        else:
            raise AssertionError('caller warnings were suppressed')


def test_warning_filters_are_restored_when_comparison_raises():
    with warnings.catch_warnings():
        warnings.resetwarnings()
        warnings.simplefilter('error', UserWarning)
        before = list(warnings.filters)

        try:
            dill.pickles(RaisesOnEquality())
        except RuntimeError as error:
            assert str(error) == 'cannot compare'
        else:
            raise AssertionError('comparison error was not raised')

        assert warnings.filters == before


def test_comparison_warnings_are_suppressed():
    with warnings.catch_warnings():
        warnings.resetwarnings()
        warnings.simplefilter('error', UserWarning)
        before = list(warnings.filters)

        assert dill.pickles(WarnsOnEquality(), exact=True)

        assert warnings.filters == before


if __name__ == '__main__':
    test_existing_ignore_filter_is_preserved()
    test_warning_filters_are_restored_after_safe_failure()
    test_warning_filters_are_restored_when_comparison_raises()
    test_comparison_warnings_are_suppressed()
