from backend.strategies.ddix.source_anchors import (
    AnchorEvidenceKind,
    DDIX_SOURCE_ANCHORS,
    VisualParityStatus,
)


def test_source_anchor_ids_are_unique():
    ids = [anchor.source_id for anchor in DDIX_SOURCE_ANCHORS]
    assert len(ids) == len(set(ids))


def test_direct_video_anchors_have_timestamps_and_remain_semantic_only():
    video = [
        anchor for anchor in DDIX_SOURCE_ANCHORS
        if anchor.evidence_kind is AnchorEvidenceKind.DIRECT_VIDEO_SEMANTIC
    ]
    assert len(video) >= 3
    assert all(anchor.timestamp_seconds is not None for anchor in video)
    assert all(
        anchor.visual_parity_status is VisualParityStatus.SEMANTIC_ONLY
        for anchor in video
    )


def test_official_nelogica_visual_supports_sign_order_but_not_numeric_formula():
    anchor = next(
        item for item in DDIX_SOURCE_ANCHORS
        if item.source_id == "NEL_DIDI_INDEX_BUY_VISUAL"
    )
    assert anchor.visual_parity_status is VisualParityStatus.SIGN_ORDER_SUPPORTED
    assert "MA3_ABOVE_ZERO" in anchor.expected_tags
    assert "MA20_BELOW_ZERO" in anchor.expected_tags


def test_false_point_course_anchor_keeps_numeric_parity_open():
    anchor = next(
        item for item in DDIX_SOURCE_ANCHORS
        if item.source_id == "CST_SECTION_12B_FALSE_POINT"
    )
    assert anchor.visual_parity_status is VisualParityStatus.NUMERIC_PARITY_OPEN
    assert "EXACT_MOMENT" in anchor.expected_tags
    assert "SLOW_POSITION" in anchor.expected_tags
