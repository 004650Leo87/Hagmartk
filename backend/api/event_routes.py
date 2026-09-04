from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query

from backend.domain.market_events import market_event_to_dict
from backend.services.hdf_event_adapter import HDFRadarService


router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/radar")
def list_event_radar(
    limit: int = Query(default=50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """Read-only internal Event Radar derived from live Shadow evidence."""
    events = HDFRadarService().list_live_radar(limit=limit)
    return [market_event_to_dict(event) for event in events]
