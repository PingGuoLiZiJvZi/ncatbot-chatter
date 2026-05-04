import pytest
from conf.schema import ActivityConfig
from core.activity_curve import ActivityCurve


class TestActivityCurve:
    def test_default_weights(self):
        cfg = ActivityConfig()
        ac = ActivityCurve(cfg)
        # Deep night should be low
        assert ac.get_weight(0) == 0.0
        assert ac.get_weight(3) == 0.0
        # Daytime should be higher
        assert ac.get_weight(15) > 0.5

    def test_get_weight_range(self):
        cfg = ActivityConfig()
        ac = ActivityCurve(cfg)
        for h in range(24):
            w = ac.get_weight(h)
            assert 0.0 <= w <= 1.0

    def test_is_sleeping_default(self):
        cfg = ActivityConfig()
        ac = ActivityCurve(cfg)
        assert ac.is_sleeping(0) is True
        assert ac.is_sleeping(3) is True
        assert ac.is_sleeping(6) is True
        assert ac.is_sleeping(7) is False
        assert ac.is_sleeping(12) is False
        assert ac.is_sleeping(23) is False

    def test_is_sleeping_wraparound(self):
        cfg = ActivityConfig(sleep_hours=(22, 6))
        ac = ActivityCurve(cfg)
        assert ac.is_sleeping(23) is True
        assert ac.is_sleeping(0) is True
        assert ac.is_sleeping(5) is True
        assert ac.is_sleeping(6) is False
        assert ac.is_sleeping(12) is False
        assert ac.is_sleeping(21) is False

    def test_hourly_weight_boundary(self):
        cfg = ActivityConfig()
        ac = ActivityCurve(cfg)
        # hour 24 should wrap to 0
        assert ac.get_weight(24) == ac.get_weight(0)
        assert ac.get_weight(25) == ac.get_weight(1)
