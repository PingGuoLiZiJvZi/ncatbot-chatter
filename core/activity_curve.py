from __future__ import annotations

from conf.schema import ActivityConfig


class ActivityCurve:
    def __init__(self, config: ActivityConfig):
        self._weights = config.hourly_weights
        self._sleep_start, self._sleep_end = config.sleep_hours

    def get_weight(self, hour: int) -> float:
        hour = hour % 24
        return self._weights[hour]

    def is_sleeping(self, hour: int | None = None) -> bool:
        if hour is None:
            from datetime import datetime
            hour = datetime.now().hour
        if self._sleep_start < self._sleep_end:
            return self._sleep_start <= hour < self._sleep_end
        else:
            return hour >= self._sleep_start or hour < self._sleep_end
