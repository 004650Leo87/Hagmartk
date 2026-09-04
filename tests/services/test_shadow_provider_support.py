from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import ScannerStatus
from backend.services.shadow_scanner import (
    SHADOW_ASSETS,
    SHADOW_TIMEFRAMES,
    ShadowScannerManager,
    resolve_supported_shadow_assets,
)
from backend.services.shadow_store import ShadowStoreRepository


class FakeCatalogAdapter:
    def __init__(self, symbols):
        self.symbols = symbols

    def get_symbols(self):
        return [{"symbol": symbol} for symbol in self.symbols]


def test_resolver_preserves_configured_universe_and_marks_missing_crypto():
    configured_without_crypto = [s for s in SHADOW_ASSETS if s not in {"BTCUSD", "ETHUSD"}]
    supported, unsupported = resolve_supported_shadow_assets(FakeCatalogAdapter(configured_without_crypto))
    assert supported == configured_without_crypto
    assert unsupported == ["BTCUSD", "ETHUSD"]
    assert len(SHADOW_ASSETS) == 13


def test_refresh_persists_provider_support_and_marks_states(tmp_path):
    repo = ShadowStoreRepository(str(tmp_path / "shadow.db"))
    scanner = ShadowScannerManager(store=repo)
    supported_symbols = [s for s in SHADOW_ASSETS if s not in {"BTCUSD", "ETHUSD"}]

    supported, unsupported = scanner.refresh_provider_support(FakeCatalogAdapter(supported_symbols))
    assert supported == supported_symbols
    assert unsupported == ["BTCUSD", "ETHUSD"]
    assert len(scanner.provider_supported_assets) * len(SHADOW_TIMEFRAMES) == 88

    support = repo.get_provider_support()
    assert support["BTCUSD"]["supported"] is False
    assert support["ETHUSD"]["supported"] is False
    state = repo.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, "BTCUSD", "M15")
    assert state.scanner_status == ScannerStatus.UNSUPPORTED_BY_PROVIDER.value


def test_unsupported_provider_failures_do_not_pollute_active_coverage(tmp_path):
    repo = ShadowStoreRepository(str(tmp_path / "shadow.db"))
    checked_at = "2026-09-04 03:40:00"
    for symbol in SHADOW_ASSETS:
        repo.save_provider_support(
            symbol,
            symbol not in {"BTCUSD", "ETHUSD"},
            "AVAILABLE_IN_PROVIDER_CATALOG" if symbol not in {"BTCUSD", "ETHUSD"} else "UNSUPPORTED_BY_PROVIDER",
            checked_at,
        )

    candidate_id = HDF_ROBUST_CANDIDATE_V1.candidate_id
    now_str = "2026-09-04T03:00:00+00:00"
    repo.record_scanner_telemetry(candidate_id, "BTCUSD", "M15", False, "MARKET_DATA_UNAVAILABLE", now_str)
    repo.record_scanner_telemetry(candidate_id, "ETHUSD", "M15", False, "MARKET_DATA_UNAVAILABLE", now_str)
    repo.record_scanner_telemetry(candidate_id, "EURUSD", "M15", True, now_str=now_str)

    telemetry = repo.get_shadow_telemetry(candidate_id)
    global_row = telemetry["global"]
    assert global_row["configured_combinations"] == 104
    assert global_row["provider_supported_combinations"] == 88
    assert global_row["provider_unsupported_combinations"] == 16
    assert global_row["unsupported_symbols"] == ["BTCUSD", "ETHUSD"]
    assert global_row["failed_checks"] == 0
    assert global_row["successful_checks"] == 1
    assert global_row["coverage"] == 1.0

    btc = next(
        row for row in telemetry["combinations"]
        if row["symbol"] == "BTCUSD" and row["timeframe"] == "M15"
    )
    assert btc["failed_checks"] == 1
    assert btc["coverage_included"] is False
    assert btc["health"] == "UNSUPPORTED_BY_PROVIDER"
