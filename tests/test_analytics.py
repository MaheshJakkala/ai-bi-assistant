import pytest

from app import analytics


def test_total_revenue_matches_completed_orders(conn):
    result = analytics.total_revenue(conn)
    assert result["data"][0]["value"] == pytest.approx(1439200.0)
    assert "1,439,200.00" in result["answer"]


def test_top_product_is_monitor(conn):
    result = analytics.revenue_by_product(conn)
    assert result["data"][0]["product"] == "Monitor"
    assert result["data"][0]["revenue"] == pytest.approx(473000.0)


def test_top_region_is_south(conn):
    result = analytics.revenue_by_region(conn)
    assert result["data"][0]["region"] == "South"
    assert result["data"][0]["revenue"] == pytest.approx(411200.0)


def test_returned_orders_excluded_by_default(conn):
    excluded = analytics.total_revenue(conn)["data"][0]["value"]
    included = analytics.total_revenue(conn, include_returned=True)["data"][0]["value"]
    assert included == pytest.approx(excluded + 2 * 9500)


def test_monthly_trend_has_six_months(conn):
    data = analytics.monthly_trend(conn)["data"]
    assert [row["month"] for row in data] == [
        "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
    ]


def test_compare_jan_and_feb(conn):
    result = analytics.compare_months(conn, 1, 2026, 2, 2026)
    assert result["meta"]["change"] == pytest.approx(24350.0)
    assert "increased" in result["answer"]


def test_month_without_data_reports_zero(conn):
    result = analytics.compare_months(conn, 12, 2026, 1, 2026)
    assert result["meta"]["from"]["revenue"] == 0.0
    assert result["meta"]["change_pct"] is None
