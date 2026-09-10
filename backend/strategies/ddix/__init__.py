"""HAGMARTK DDIX research-only strategy references."""

from .public_reference import (
    ClassicNeedleEvidence,
    DidiIndexLines,
    DidiIndexMethod,
    FalsePointEvidence,
    FalsePointKind,
    IndexedAlignment,
    IndexedAlignmentEvidence,
    MovingAverages3820,
    NeedleDirection,
    classify_classic_needle_snapshot,
    classify_false_point_candidate,
    classify_indexed_alignment,
    compute_didi_index_lines,
    compute_moving_averages_3_8_20,
    simple_moving_average,
)
from .source_anchors import (
    AnchorEvidenceKind,
    DDIX_SOURCE_ANCHORS,
    SourceAnchor,
    VisualParityStatus,
)

__all__ = [
    "AnchorEvidenceKind", "ClassicNeedleEvidence", "DDIX_SOURCE_ANCHORS",
    "DidiIndexLines", "DidiIndexMethod", "FalsePointEvidence",
    "FalsePointKind", "IndexedAlignment", "IndexedAlignmentEvidence",
    "MovingAverages3820", "NeedleDirection", "SourceAnchor",
    "VisualParityStatus", "classify_classic_needle_snapshot",
    "classify_false_point_candidate", "classify_indexed_alignment",
    "compute_didi_index_lines", "compute_moving_averages_3_8_20",
    "simple_moving_average",
]
