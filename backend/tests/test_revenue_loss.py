from analysis.revenue_loss import get_revenue_loss

def test_returns_list():
    result = get_revenue_loss()
    assert isinstance(result, list)

def test_has_required_fields():
    result = get_revenue_loss()
    if result:
        row = result[0]
        assert "state" in row
        assert "estimated_loss_cr" in row
        assert "avg_gap_per_quintal" in row

def test_loss_is_non_negative():
    result = get_revenue_loss()
    for row in result:
        assert row["estimated_loss_cr"] >= 0
