"""Metrics for observability (message counts, delivery latency, etc.)."""

from typing import Dict


class Metrics:
    """In-memory metrics collector for pub-sub events."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, int] = {}

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter."""
        self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: int) -> None:
        """Set a gauge value."""
        self._gauges[name] = value

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> int:
        return self._gauges.get(name, 0)

    def snapshot(self) -> Dict[str, Dict[str, int]]:
        """Return a snapshot of all metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }
