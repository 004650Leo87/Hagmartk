"""HAGMARTK DDIX research-only strategy references."""

from .public_reference import (
    ClassicNeedleEvidence,
    DidiIndexLines,
    DidiIndexMethod,
    FalsePointEvidence,
    FalsePointKind,
    MovingAverages3820,
    NeedleDirection,
    classify_classic_needle_snapshot,
    classify_false_point_candidate,
    compute_didi_index_lines,
    compute_moving_averages_3_8_20,
    simple_moving_average,
)

__all__ = [
    "ClassicNeedleEvidence", "DidiIndexLines", "DidiIndexMethod",
    "FalsePointEvidence", "FalsePointKind", "MovingAverages3820",
    "NeedleDirection", "classify_classic_needle_snapshot",
    "classify_false_point_candidate", "compute_didi_index_lines",
    "compute_moving_averages_3_8_20", "simple_moving_average",
]
