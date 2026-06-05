# backend/tests/test_regional_recency.py
from analysis.regional_fit import _recency_weight


def test_recency_weight_newer_year_higher():
    # max_year=2015, window=10 -> 2006..2015
    assert _recency_weight(2015, 2015, 10) > _recency_weight(2006, 2015, 10)


def test_recency_weight_in_unit_range():
    for y in range(2006, 2016):
        w = _recency_weight(y, 2015, 10)
        assert 0.0 < w <= 1.0


def test_recency_weight_oldest_is_floor():
    # oldest year in window gets the minimum (1/window), newest gets 1.0
    assert _recency_weight(2006, 2015, 10) == round(1 / 10, 4)
    assert _recency_weight(2015, 2015, 10) == 1.0
