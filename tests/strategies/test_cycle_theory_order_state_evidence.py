from types import SimpleNamespace

from backend.strategies.cycle_theory.mt5_order_state_evidence import collect_order_state_evidence


class FakeMT5:
    ORDER_STATE_FILLED = 4
    ORDER_STATE_CANCELED = 2
    ORDER_STATE_REJECTED = 6

    def history_orders_get(self, _start, _end):
        return [
            SimpleNamespace(state=4, symbol="XAUUSD"),
            SimpleNamespace(state=2, symbol="XAUUSD"),
            SimpleNamespace(state=6, symbol="XAUUSD"),
            SimpleNamespace(state=6, symbol="EURUSD"),
        ]


def test_collect_order_state_evidence_is_read_only_and_counts_terminal_states():
    fake = FakeMT5()
    result = collect_order_state_evidence(fake)
    assert result["total_orders"] == 4
    assert result["by_state"]["ORDER_STATE_FILLED"] == 1
    assert result["canceled_count"] == 1
    assert result["rejected_count"] == 2
    assert result["rejected_symbols"] == ["EURUSD", "XAUUSD"]
    assert not hasattr(fake, "order_send")

