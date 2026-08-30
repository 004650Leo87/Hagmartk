"""Gate 3N: calculation-only MT5 margin evidence contract."""
from types import SimpleNamespace
import pytest
from backend.strategies.cycle_theory.mt5_margin_evidence import capture_buy_margin_evidence


def _fake_mt5(margin=231.65):
    calls = []
    fake = SimpleNamespace(ORDER_TYPE_BUY=0)
    fake.symbol_info = lambda symbol: SimpleNamespace(name=symbol)
    fake.symbol_info_tick = lambda symbol: SimpleNamespace(ask=1.15824)
    fake.account_info = lambda: SimpleNamespace(currency="USD", leverage=500, server="TEST")
    def calc(order_type, symbol, volume, price):
        calls.append((order_type, symbol, volume, price))
        return margin
    fake.order_calc_margin = calc
    fake.last_error = lambda: (1, "Success")
    fake.calls = calls
    return fake


def test_capture_uses_buy_margin_calculation_only():
    mt5 = _fake_mt5()
    evidence = capture_buy_margin_evidence(mt5, "EURUSD", 1.0)
    assert evidence.margin == 231.65
    assert mt5.calls == [(mt5.ORDER_TYPE_BUY, "EURUSD", 1.0, 1.15824)]
    assert not hasattr(mt5, "order_send")
