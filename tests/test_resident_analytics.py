"""Compatibility facade for the decomposed test_resident_analytics interfaces."""




import polars as pl
import pytest
from test_resident_analytics_base import HTTP_CLIENT as HTTP_CLIENT
from test_resident_analytics_governance import FixtureProvider as FixtureProvider
from test_resident_analytics_transport import mock_client as mock_client

from hmt_edge_robot.resident import HealthModel


def test_analytics_actual_engines_and_parquet(cell, ready, tmp_path):
    summary = cell.analytics.summary()
    assert sum(r["event_count"] for r in summary) == 3
    cell.observe_simulation(1, temp_c=86.0)
    trends = cell.analytics.sensor_trends()
    assert trends == {"sample_count": 2, "gap_count": 1, "mean_temp_c": 45.0}
    path = tmp_path / "archive.parquet"
    assert cell.analytics.export_parquet(path) == 5
    assert pl.read_parquet(path).height == 5
    assert cell.analytics.frame(1).height == 1

def test_empty_analytics(cell):
    assert cell.analytics.summary() == []
    assert cell.analytics.sensor_trends()["sample_count"] == 0

def test_classical_ml_fit_inference_and_determinism():
    model, other = HealthModel(), HealthModel()
    assert model.predict(4.0, 45.0)["decision"] == "HOLD"
    baseline = tuple((4.0 + 0.02 * (i % 9), 43.0 + (i % 7)) for i in range(32))
    assert model.fit(baseline) == other.fit(baseline)
    assert model.predict(3.0, 90.0)["decision"] == "HOLD"
    assert model.predict(4.08, 46.0) == other.predict(4.08, 46.0)
    for invalid in ((), ((float("nan"), 0.0),) * 16, ((4.0, 45.0),) * 16):
        with pytest.raises(ValueError):
            model.fit(invalid)
    with pytest.raises(ValueError):
        model.predict(float("inf"), 1.0)
