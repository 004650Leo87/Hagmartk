from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.services.orb_shadow import OrbProspectiveScanner
from backend.services.orb_shadow_store import OrbShadowStore


class FakeNotifier:
    def __init__(self):
        self.events = []
    def notify_orb_async(self, event_type, event):
        self.events.append((event_type, dict(event)))
        return True


class FakeCapture:
    def __init__(self):
        self.quote = None
        self.trigger = None
        self.watches = []
    def update_symbols(self, symbols):
        self.symbols = list(symbols)
    def wait_first_quote(self, symbol, boundary, deadline):
        return dict(self.quote) if self.quote else None
    def register_watch(self, symbol, direction, stop, target, t120, entry_time):
        self.watches.append((symbol, direction, stop, target, t120, entry_time))
    def pop_trigger(self, symbol):
        row, self.trigger = self.trigger, None
        return dict(row) if row else None
    def start(self):
        return None
    def stop(self):
        return None
    def status(self):
        return {"running": True, "source": "FAKE"}


class FakeAdapter:
    def __init__(self):
        self.binance = self
    def get_symbols(self):
        return [{
            "symbol": "TESTUSDT", "provider": "BINANCE_USDM_FUTURES", "category": "CRYPTO",
            "contract_type": "PERPETUAL", "instrument_id": "BINANCE_USDM_FUTURES:TESTUSDT",
            "settle_asset": "USDT", "currency_profit": "USDT", "point": 1.0,
            "volume_min": 1.0, "volume_max": 1000.0, "volume_step": 1.0,
            "trade_contract_size": 1.0,
        }]
    def get_mark_price(self, symbol):
        return {"next_funding_time": int(datetime(2026, 9, 9, 8, tzinfo=timezone.utc).timestamp() * 1000),
                "last_funding_rate": 0.0001, "mark_price": 105.0}
    def get_funding_rates(self, symbol, from_time, to_time):
        return []
    def get_candles(self, symbol, timeframe, count=None, **kwargs):
        t0 = datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)
        values = [
            (100, 105, 100, 103),
            (103, 110, 102, 109),
            (109, 109, 101, 105),
            (105, 112, 104, 111),
        ]
        rows = []
        for i, (o, h, l, c) in enumerate(values):
            rows.append({"time": (t0 + timedelta(minutes=5*i)).isoformat(),
                         "open": o, "high": h, "low": l, "close": c})
        return rows[-int(count or len(rows)):]

def _scanner(tmp_path: Path):
    store = OrbShadowStore(str(tmp_path / "orb.db"))
    notifier = FakeNotifier()
    scanner = OrbProspectiveScanner(store=store, notifier=notifier, max_workers=8)
    scanner.adapter = FakeAdapter()
    scanner.capture = FakeCapture()
    scanner.refresh_universe()
    return scanner, store, notifier


def test_prospective_orb_builds_range_signals_and_enters_once(tmp_path):
    scanner, store, notifier = _scanner(tmp_path)
    t0 = datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)
    scanner.run_cycle(t0 + timedelta(minutes=1))
    scanner.run_cycle(t0 + timedelta(minutes=15, seconds=1))
    rows = store.sessions_for_t0(t0.isoformat())
    assert len(rows) == 1
    assert rows[0]["state"] == "WAIT_SIGNAL"
    assert rows[0]["range_high"] == "110"
    assert rows[0]["range_low"] == "100"

    scanner.capture.quote = {
        "symbol": "TESTUSDT", "bid": 111.0, "ask": 112.0,
        "time": (t0 + timedelta(minutes=20, milliseconds=100)).isoformat(),
        "source": "FAKE_FIRST_QUOTE",
    }
    scanner.run_cycle(t0 + timedelta(minutes=20, seconds=1))
    row = store.sessions_for_t0(t0.isoformat())[0]
    assert row["state"] == "OPEN"
    assert row["opportunity_consumed"] == 1
    assert row["direction"] == "LONG"
    assert row["entry_price"] == "113.0"
    assert row["stop_price"] == "99.0"
    assert row["target_price"] == "141.0"
    assert len(scanner.capture.watches) == 1
    types = [item[0] for item in notifier.events]
    assert types.count("SIGNAL") == 1
    assert types.count("ENTRY_FILLED") == 1

def _open_trade(scanner, store):
    t0 = datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc)
    scanner.run_cycle(t0 + timedelta(minutes=1))
    scanner.run_cycle(t0 + timedelta(minutes=15, seconds=1))
    scanner.capture.quote = {
        "symbol": "TESTUSDT", "bid": 111.0, "ask": 112.0,
        "time": (t0 + timedelta(minutes=20, milliseconds=100)).isoformat(),
        "source": "FAKE_FIRST_QUOTE",
    }
    scanner.run_cycle(t0 + timedelta(minutes=20, seconds=1))
    return t0, store.sessions_for_t0(t0.isoformat())[0]


def test_prospective_orb_closes_from_event_sequenced_target(tmp_path):
    scanner, store, notifier = _scanner(tmp_path)
    t0, row = _open_trade(scanner, store)
    scanner.capture.trigger = {
        "reason": "TARGET",
        "quote": {"symbol": "TESTUSDT", "bid": 142.0, "ask": 143.0,
                  "time": (t0 + timedelta(minutes=25)).isoformat()},
    }
    scanner.run_cycle(t0 + timedelta(minutes=25, seconds=1))
    row = store.sessions_for_t0(t0.isoformat())[0]
    assert row["state"] == "DONE"
    assert row["exit_reason"] == "TARGET"
    assert row["exit_price"] == "141.0"
    assert row["r_multiple"] is not None
    assert any(event[0] == "EXIT_FILLED" for event in notifier.events)


def test_prospective_orb_marks_stream_gap_unresolved(tmp_path):
    scanner, store, notifier = _scanner(tmp_path)
    t0, row = _open_trade(scanner, store)
    scanner.capture.trigger = {
        "reason": "DATA_GAP",
        "quote": {"symbol": "TESTUSDT", "bid": 110.0, "ask": 111.0,
                  "time": (t0 + timedelta(minutes=25)).isoformat()},
    }
    scanner.run_cycle(t0 + timedelta(minutes=25, seconds=1))
    row = store.sessions_for_t0(t0.isoformat())[0]
    assert row["state"] == "ERROR_RECONCILE"
    assert "DATA_STREAM_GAP" in row["rejection_reason"]
    assert any(event[0] == "EXIT_UNRESOLVED" for event in notifier.events)
