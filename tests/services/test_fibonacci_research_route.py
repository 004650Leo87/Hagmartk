from backend.api import shadow_routes


def test_fibonacci_research_route_is_read_only(monkeypatch):
    class FakeEngine:
        def build_research_summary(self, candidate_id: str):
            return {
                "candidate_id": candidate_id,
                "research_state": "RESEARCH_ONLY",
                "promotion_allowed": False,
            }

    monkeypatch.setattr(shadow_routes, "_fib_engine", FakeEngine())
    result = shadow_routes.get_fibonacci_research("hdf_dvp_exit_2r")

    assert result["candidate_id"] == "hdf_dvp_exit_2r"
    assert result["promotion_allowed"] is False

    route = next(r for r in shadow_routes.router.routes if r.path == "/api/shadow/fibonacci-research")
    assert route.methods == {"GET"}
