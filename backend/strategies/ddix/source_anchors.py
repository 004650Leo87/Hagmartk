from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class AnchorEvidenceKind(str, Enum):
    OFFICIAL_VISUAL = "OFFICIAL_VISUAL"
    DIRECT_VIDEO_SEMANTIC = "DIRECT_VIDEO_SEMANTIC"
    COURSE_TEXT_SEMANTIC = "COURSE_TEXT_SEMANTIC"


class VisualParityStatus(str, Enum):
    SIGN_ORDER_SUPPORTED = "SIGN_ORDER_SUPPORTED"
    SEMANTIC_ONLY = "SEMANTIC_ONLY"
    NUMERIC_PARITY_OPEN = "NUMERIC_PARITY_OPEN"


@dataclass(frozen=True)
class SourceAnchor:
    source_id: str
    title: str
    url: str
    evidence_kind: AnchorEvidenceKind
    expected_tags: Tuple[str, ...]
    visual_parity_status: VisualParityStatus
    timestamp_seconds: int | None = None


DDIX_SOURCE_ANCHORS: Tuple[SourceAnchor, ...] = (
    SourceAnchor(
        source_id="NEL_DIDI_INDEX_BUY_VISUAL",
        title="Nelogica Didi Index — official buy example",
        url="https://ajuda.nelogica.com.br/hc/pt-br/articles/13161968774299-Didi-Index",
        evidence_kind=AnchorEvidenceKind.OFFICIAL_VISUAL,
        expected_tags=(
            "MA3_ABOVE_ZERO",
            "MA8_REFERENCE_ZERO",
            "MA20_BELOW_ZERO",
            "BULLISH_ALIGNMENT",
        ),
        visual_parity_status=VisualParityStatus.SIGN_ORDER_SUPPORTED,
    ),
    SourceAnchor(
        source_id="DIDI_VIDEO_AGULHADAS_012204",
        title="DIDI Agulhada PARTE 1/3 — agulhadas e algoritmos gráficos",
        url="https://www.youtube.com/watch?v=epeLGFv7WCg",
        evidence_kind=AnchorEvidenceKind.DIRECT_VIDEO_SEMANTIC,
        expected_tags=("AGULHADA", "MULTI_TIMEFRAME_CONTEXT"),
        visual_parity_status=VisualParityStatus.SEMANTIC_ONLY,
        timestamp_seconds=4924,
    ),
    SourceAnchor(
        source_id="DIDI_VIDEO_FALSE_MOVES_013008",
        title="DIDI Agulhada PARTE 1/3 — movimentos falsos",
        url="https://www.youtube.com/watch?v=epeLGFv7WCg",
        evidence_kind=AnchorEvidenceKind.DIRECT_VIDEO_SEMANTIC,
        expected_tags=("FALSE_MOVE_CONTEXT", "TREND_CONTINUATION_CONTEXT"),
        visual_parity_status=VisualParityStatus.SEMANTIC_ONLY,
        timestamp_seconds=5408,
    ),
    SourceAnchor(
        source_id="DIDI_VIDEO_FALSE_POINT_TREND_020741",
        title="DIDI Agulhada PARTE 1/3 — tendência e pontos falsos",
        url="https://www.youtube.com/watch?v=epeLGFv7WCg",
        evidence_kind=AnchorEvidenceKind.DIRECT_VIDEO_SEMANTIC,
        expected_tags=("FALSE_POINT", "TREND_CONTEXT", "MULTI_TIMEFRAME_CONTEXT"),
        visual_parity_status=VisualParityStatus.SEMANTIC_ONLY,
        timestamp_seconds=7661,
    ),
    SourceAnchor(
        source_id="CST_SECTION_12B_FALSE_POINT",
        title="Apostila CST — 12B Como encontramos um Ponto Falso",
        url="https://pt.scribd.com/document/633888572/Apostila-Didi-CST-pdf",
        evidence_kind=AnchorEvidenceKind.COURSE_TEXT_SEMANTIC,
        expected_tags=("FALSE_POINT", "EXACT_MOMENT", "FAST_VS_REFERENCE", "SLOW_POSITION"),
        visual_parity_status=VisualParityStatus.NUMERIC_PARITY_OPEN,
    ),
)
