from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Dict


@dataclass
class ExecutionProfiler:
    """Registrador de profiling de tempo de execução com medições reais por fase."""

    data_acquisition_time: float = 0.0
    indicator_calc_time: float = 0.0
    backtest_time: float = 0.0
    reconciliation_time: float = 0.0
    walk_forward_time: float = 0.0
    monte_carlo_time: float = 0.0
    parameter_robustness_time: float = 0.0
    total_time: float = 0.0
    workers_used: int = 1
    measured_speedup: float = 1.0

    _start_times: Dict[str, float] = field(default_factory=dict)

    def start_timer(self, phase_name: str) -> None:
        self._start_times[phase_name] = time.perf_counter()

    def stop_timer(self, phase_name: str) -> float:
        start = self._start_times.get(phase_name)
        if start is None:
            return 0.0
        elapsed = time.perf_counter() - start
        setattr(self, phase_name, getattr(self, phase_name, 0.0) + elapsed)
        return elapsed

    def to_dict(self) -> Dict[str, float]:
        return {
            "data_acquisition_time_sec": round(self.data_acquisition_time, 4),
            "indicator_calc_time_sec": round(self.indicator_calc_time, 4),
            "backtest_time_sec": round(self.backtest_time, 4),
            "reconciliation_time_sec": round(self.reconciliation_time, 4),
            "walk_forward_time_sec": round(self.walk_forward_time, 4),
            "monte_carlo_time_sec": round(self.monte_carlo_time, 4),
            "parameter_robustness_time_sec": round(self.parameter_robustness_time, 4),
            "total_time_sec": round(self.total_time, 4),
            "workers_used": self.workers_used,
            "measured_speedup": round(self.measured_speedup, 2),
        }
