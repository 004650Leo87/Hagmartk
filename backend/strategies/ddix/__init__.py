"""HAGMARTK DDIX research-only strategy references."""

from .bollinger_reference import (
    BollingerOpeningEvidence,
    BollingerSnapshot,
    DDIX_BOLLINGER_DEVIATION_CANDIDATE,
    DDIX_BOLLINGER_PERIOD_CANDIDATE,
    classify_bollinger_opening_candidate,
    compute_bollinger_snapshot,
    population_stddev,
)
from .dmi_platform_parity import (
    DmiParityReport,
    PlatformDmiRow,
    compare_platform_rows,
    load_platform_csv,
)
from .dmi_reference import (
    AdxKickEvidence,
    DidiTrendState,
    DmiContextEvidence,
    DmiDirection,
    DmiSnapshot,
    classify_adx_kick_candidate,
    classify_didi_dmi_context,
)
from .dmi_wilder import (
    OhlcBar,
    WilderDmiPoint,
    WilderDmiStream,
    calculate_metaquotes_wilder_batch,
    calculate_metaquotes_wilder_streaming,
)
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
    "AdxKickEvidence", "AnchorEvidenceKind", "BollingerOpeningEvidence",
    "BollingerSnapshot", "ClassicNeedleEvidence", "DDIX_BOLLINGER_DEVIATION_CANDIDATE",
    "DDIX_BOLLINGER_PERIOD_CANDIDATE", "DDIX_SOURCE_ANCHORS", "DidiIndexLines",
    "DidiIndexMethod", "DidiTrendState", "DmiContextEvidence", "DmiDirection",
    "DmiParityReport", "DmiSnapshot", "FalsePointEvidence", "FalsePointKind",
    "IndexedAlignment", "IndexedAlignmentEvidence", "MovingAverages3820",
    "NeedleDirection", "OhlcBar", "PlatformDmiRow", "SourceAnchor",
    "VisualParityStatus", "WilderDmiPoint", "WilderDmiStream",
    "calculate_metaquotes_wilder_batch", "calculate_metaquotes_wilder_streaming",
    "classify_adx_kick_candidate", "classify_bollinger_opening_candidate",
    "classify_classic_needle_snapshot", "classify_didi_dmi_context",
    "classify_false_point_candidate", "classify_indexed_alignment",
    "compare_platform_rows", "compute_bollinger_snapshot", "compute_didi_index_lines",
    "compute_moving_averages_3_8_20", "load_platform_csv", "population_stddev",
    "simple_moving_average",
]
