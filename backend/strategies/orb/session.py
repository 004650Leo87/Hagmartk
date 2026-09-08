from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Optional

from .models import SessionState, Signal


@dataclass
class OrbSessionStateMachine:
    session_id: str
    state: SessionState = SessionState.WAIT_SESSION
    opportunity_consumed: bool = False
    entry_request_consumed: bool = False
    signal_id: str = ""
    quantity_filled: Decimal = Decimal("0")
    data_gap_after_entry: bool = False
    reconcile_reason: str = ""

    def begin_range(self) -> None:
        if self.state is SessionState.WAIT_SESSION:
            self.state = SessionState.BUILD_RANGE

    def freeze_range(self) -> None:
        if self.state is not SessionState.BUILD_RANGE:
            raise ValueError("INVALID_STATE_TRANSITION")
        self.state = SessionState.WAIT_SIGNAL

    def register_signal(self, signal: Signal) -> bool:
        if signal.session_id != self.session_id:
            raise ValueError("SESSION_ID_MISMATCH")
        if self.opportunity_consumed or self.state is not SessionState.WAIT_SIGNAL:
            return False
        self.opportunity_consumed = True
        self.signal_id = signal.signal_id
        self.state = SessionState.ENTRY_PENDING
        return True

    def register_entry_request(self) -> bool:
        if self.state is not SessionState.ENTRY_PENDING or self.entry_request_consumed:
            return False
        self.entry_request_consumed = True
        return True

    def register_entry_fill(self, quantity: Decimal) -> None:
        if self.state is not SessionState.ENTRY_PENDING or not self.entry_request_consumed:
            raise ValueError("INVALID_STATE_TRANSITION")
        quantity = Decimal(quantity)
        if quantity <= 0:
            raise ValueError("INVALID_FILL_QUANTITY")
        self.quantity_filled += quantity
        self.state = SessionState.OPEN

    def register_entry_rejection(self) -> None:
        if self.quantity_filled > 0:
            self.state = SessionState.ERROR_RECONCILE
            self.reconcile_reason = "ENTRY_REJECTION_WITH_EXPOSURE"
        else:
            self.state = SessionState.SKIPPED

    def register_data_gap(self) -> None:
        if self.quantity_filled > 0:
            self.data_gap_after_entry = True

    def request_exit(self) -> None:
        if self.state is not SessionState.OPEN:
            raise ValueError("INVALID_STATE_TRANSITION")
        self.state = SessionState.EXIT_PENDING

    def confirm_flat(self) -> None:
        if self.state not in (SessionState.EXIT_PENDING, SessionState.ERROR_RECONCILE):
            raise ValueError("INVALID_STATE_TRANSITION")
        self.quantity_filled = Decimal("0")
        self.state = SessionState.DONE

    def protection_failure(self) -> None:
        if self.quantity_filled <= 0:
            raise ValueError("PROTECTION_FAILURE_WITHOUT_EXPOSURE")
        self.state = SessionState.ERROR_RECONCILE
        self.reconcile_reason = "PROTECTION_FAILURE"

    def mark_no_signal_before_cutoff(self) -> None:
        if self.state is SessionState.WAIT_SIGNAL:
            self.state = SessionState.SKIPPED

    def snapshot(self) -> dict:
        row = asdict(self)
        row["state"] = self.state.value
        row["quantity_filled"] = format(self.quantity_filled, "f")
        return row

    @classmethod
    def restore(cls, payload: dict) -> "OrbSessionStateMachine":
        return cls(
            session_id=str(payload["session_id"]),
            state=SessionState(payload["state"]),
            opportunity_consumed=bool(payload.get("opportunity_consumed", False)),
            entry_request_consumed=bool(payload.get("entry_request_consumed", False)),
            signal_id=str(payload.get("signal_id", "")),
            quantity_filled=Decimal(str(payload.get("quantity_filled", "0"))),
            data_gap_after_entry=bool(payload.get("data_gap_after_entry", False)),
            reconcile_reason=str(payload.get("reconcile_reason", "")),
        )
