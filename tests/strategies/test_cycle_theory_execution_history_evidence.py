from types import SimpleNamespace

from backend.strategies.cycle_theory.mt5_execution_history_evidence import (
    collect_execution_pairs,
    summarize_execution_evidence,
)


class FakeMT5:
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_REASON_SL = 4
    ORDER_REASON_TP = 5
    DEAL_REASON_SL = 4
    DEAL_REASON_TP = 5

    def history_orders_get(self, start, end):
        return [
            SimpleNamespace(ticket=10, symbol="XAUUSD", type=2, reason=3, price_open=100.0),
            SimpleNamespace(ticket=20, symbol="XAUUSD", type=1, reason=4, price_open=95.0),
        ]

    def history_deals_get(self, start, end):
        return [
            SimpleNamespace(order=10, reason=3, entry=0, price=99.8, volume=0.1),
            SimpleNamespace(order=20, reason=4, entry=1, price=94.5, volume=0.1),
        ]


def test_history_evidence_joins_orders_to_deals_read_only():
    fake = FakeMT5()
    pairs = collect_execution_pairs(fake, days=30)
    assert len(pairs) == 2
    assert pairs[0].delta == -0.2
    assert pairs[1].delta == -0.5


def test_summary_exposes_nonzero_limit_and_sl_tp_execution_delta():
    fake = FakeMT5()
    summary = summarize_execution_evidence(fake, collect_execution_pairs(fake))
    assert summary["pending_limit"]["count"] == 1
    assert summary["pending_limit"]["nonzero_delta_count"] == 1
    assert summary["sl_tp"]["count"] == 1
    assert summary["sl_tp"]["nonzero_delta_count"] == 1


def test_module_has_no_order_send_surface():
    import backend.strategies.cycle_theory.mt5_execution_history_evidence as module
    source = open(module.__file__, encoding="utf-8").read()
    assert "order_send(" not in source
    assert "position_modify(" not in source
