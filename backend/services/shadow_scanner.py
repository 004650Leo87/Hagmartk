from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional
import pandas as pd

from backend.backtest.data_cache import OHLCDataCache
from backend.core.time_utils import format_utc_str, now_utc_datetime, now_utc_str, parse_utc_timestamp
from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH, HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import (
    EvidencePayload,
    ScannerStatus,
    ShadowEvent,
    ShadowEventType,
    ShadowScannerState,
    ShadowState,
)
from backend.services.alert_engine import InternalAlertEngine, InternalShadowPublisher
from backend.services.shadow_store import ShadowStoreRepository
from backend.strategies.hdf.strategy import HDFStrategy, PatternAssociationPolicy, VolumeObservationPolicy

_logger = logging.getLogger(__name__)

FOREX_ASSETS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
METALS_ASSETS = ["XAUUSD", "XAGUSD"]
CRYPTO_ASSETS = ["BTCUSD", "ETHUSD"]

SHADOW_ASSETS = FOREX_ASSETS + METALS_ASSETS + CRYPTO_ASSETS
SHADOW_TIMEFRAMES = ["M15", "H1", "H4"]


def get_asset_class(symbol: str) -> str:
    if symbol in FOREX_ASSETS:
        return "FOREX"
    elif symbol in METALS_ASSETS:
        return "METALS"
    elif symbol in CRYPTO_ASSETS:
        return "CRYPTO"
    return "UNKNOWN"


def get_only_closed_candles(
    df: pd.DataFrame, timeframe: str, now_dt: Optional[datetime] = None
) -> pd.DataFrame:
    """Filtra o DataFrame para garantir que barras ainda em formação não sejam incluídas."""
    if df.empty:
        return df

    if now_dt is None:
        now_dt = now_utc_datetime()

    tf_minutes = {"M15": 15, "H1": 60, "H4": 240}.get(timeframe.upper(), 15)

    last_time_str = str(df["time"].iloc[-1])
    last_dt = parse_utc_timestamp(last_time_str)

    if last_dt is not None:
        candle_end_dt = last_dt + timedelta(minutes=tf_minutes)
        if candle_end_dt > now_dt:
            # A última barra ainda está em formação; remove do conjunto de decisão
            return df.iloc[:-1]

    return df


class ShadowScannerManager:
    """Gerenciador do Scanner Prospectivo do Shadow Mode para 39 combinações de mercado."""

    def __init__(
        self,
        store: Optional[ShadowStoreRepository] = None,
        cache: Optional[OHLCDataCache] = None,
    ) -> None:
        self.store = store or ShadowStoreRepository()
        self.cache = cache or OHLCDataCache()
        self.publisher = InternalShadowPublisher(self.store)

        self.strategy = HDFStrategy(
            variant="HDF_DVP",
            rsi_period=14,
            pivot_left=2,
            pivot_right=2,
            min_bars_between_pivots=5,
            max_bars_between_pivots=50,
            volume_min_relative=1.0,
            max_activation_bars=5,
            activation_policy="NEXT_BAR",
            execution_buffer=0.0,
            stop_buffer=0.0,
            volume_observation_policy=VolumeObservationPolicy.CONFLUENCE_CANDLE,
            pattern_association_policy=PatternAssociationPolicy.SAME_BAR,
        )

        # Tentar restaurar sessão Shadow persistida (Recovery)
        session = self.store.get_shadow_session(HDF_ROBUST_CANDIDATE_V1.candidate_id)
        if session and session.get("started_at"):
            self.enabled = session.get("enabled", True)
            self.shadow_started_at = session["started_at"]
            _logger.info(
                "[SHADOW] RECOVERY: shadow_started_at=%s restaurado do banco",
                self.shadow_started_at,
            )
        else:
            self.enabled = True
            self.shadow_started_at = now_utc_str()
            self.store.save_shadow_session(
                HDF_ROBUST_CANDIDATE_V1.candidate_id, self.shadow_started_at, self.enabled
            )
            _logger.info(
                "[SHADOW] SHADOW_BOOTSTRAP: nova sessão Shadow criada em %s",
                self.shadow_started_at,
            )

    def enable_shadow(self) -> None:
        self.enabled = True
        if not self.shadow_started_at:
            self.shadow_started_at = now_utc_str()
        self.store.save_shadow_session(
            HDF_ROBUST_CANDIDATE_V1.candidate_id, self.shadow_started_at, self.enabled
        )
        _logger.info("[SHADOW] SHADOW_BOOTSTRAP: Shadow Mode ativado em %s", self.shadow_started_at)
        for sym in SHADOW_ASSETS:
            for tf in SHADOW_TIMEFRAMES:
                st = ShadowScannerState(
                    candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id,
                    symbol=sym,
                    timeframe=tf,
                    enabled=True,
                    scanner_status=ScannerStatus.RUNNING.value,
                )
                self.store.save_scanner_state(st)

    def disable_shadow(self) -> None:
        self.enabled = False
        self.store.save_shadow_session(
            HDF_ROBUST_CANDIDATE_V1.candidate_id, self.shadow_started_at, False
        )
        for sym in SHADOW_ASSETS:
            for tf in SHADOW_TIMEFRAMES:
                st = self.store.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, sym, tf)
                if st:
                    st.enabled = False
                    st.scanner_status = ScannerStatus.DISABLED.value
                    self.store.save_scanner_state(st)

    def scan_closed_candle(
        self,
        symbol: str,
        timeframe: str,
        df_candles: pd.DataFrame,
        is_synthetic: bool = False,
    ) -> List[ShadowEvent]:
        """Processa a chegada de um NOVO CANDLE FECHADO para um símbolo/timeframe especifico.

        REGRAS DE SEGURANÇA E REGULARIDADE:
        1. Executa SOMENTE sobre candles fechados (nunca candle em formação).
        2. Warmup histórico é utilizado EXCLUSIVAMENTE para cálculo de indicadores (RSI, pivôs, volume MA20).
        3. Apenas ocorrências com decisão prospectiva são salvas no banco.
        """
        if not self.enabled and not is_synthetic:
            return []

        now_str = now_utc_str()
        shadow_dt = self._parse_shadow_started_at()

        # Atualiza estado do scanner
        st = self.store.get_scanner_state(
            HDF_ROBUST_CANDIDATE_V1.candidate_id, symbol, timeframe
        ) or ShadowScannerState(
            candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id, symbol=symbol, timeframe=timeframe
        )

        if df_candles.empty:
            st.scanner_status = ScannerStatus.WAITING_NEW_CANDLE.value
            st.last_scan_at = now_str
            self.store.save_scanner_state(st)
            self.store.record_scanner_telemetry(
                HDF_ROBUST_CANDIDATE_V1.candidate_id, symbol, timeframe, success=False, error_code="MARKET_DATA_UNAVAILABLE", now_str=now_str
            )
            return []

        # Garantir que operamos SOMENTE sobre candles fechados
        df_closed = get_only_closed_candles(df_candles, timeframe) if not is_synthetic else df_candles

        if df_closed.empty or len(df_closed) < 25:
            st.scanner_status = ScannerStatus.WAITING_NEW_CANDLE.value
            st.last_scan_at = now_str
            self.store.save_scanner_state(st)
            self.store.record_scanner_telemetry(
                HDF_ROBUST_CANDIDATE_V1.candidate_id, symbol, timeframe, success=False, error_code="INSUFFICIENT_CANDLES", now_str=now_str
            )
            return []

        last_closed_time = str(df_closed["time"].iloc[-1])

        if st.last_processed_candle == last_closed_time and not is_synthetic:
            _logger.debug(
                "[SHADOW] DUPLICATE_SKIPPED: candle %s %s %s já processado",
                symbol, timeframe, last_closed_time,
            )
            return []

        _logger.info(
            "[SHADOW] NEW_CLOSED_CANDLE: symbol=%s tf=%s candle_time=%s scan_time=%s",
            symbol, timeframe, last_closed_time, now_str,
        )

        # Registra telemetria de sucesso na varredura da combinação
        self.store.record_scanner_telemetry(
            HDF_ROBUST_CANDIDATE_V1.candidate_id, symbol, timeframe, success=True, now_str=now_str
        )

        # Avalia a estratégia completa no conjunto de candles (warmup incluso)
        analysis = self.strategy.evaluate_full_dataset_analysis(df_closed, symbol, timeframe)
        occurrences = analysis.get("occurrences", [])

        generated_events: List[ShadowEvent] = []

        for occ in occurrences:
            state_val = occ.state.value

            if state_val not in (
                "ARMED", "ACTIVATED", "TARGET_HIT", "STOP_HIT", "EXPIRED", "INVALIDATED_BEFORE_ACTIVATION"
            ):
                continue

            event_time_str = str(occ.divergence.candle2.time)
            event_dt = self._parse_event_time(event_time_str)

            is_bootstrap = False
            classification = "NEW_PROSPECTIVE_EVENT"

            # Verificação de prospectividade contra T0 (shadow_started_at)
            if shadow_dt is not None and event_dt is not None:
                if event_dt < shadow_dt:
                    # Ocorrência com referência temporal anterior a T0
                    if state_val in (
                        "TARGET_HIT", "STOP_HIT", "EXPIRED", "INVALIDATED_BEFORE_ACTIVATION"
                    ) or (
                        state_val == "ACTIVATED"
                        and self._parse_event_time(str(occ.activation_time or event_time_str)) < shadow_dt
                    ):
                        _logger.info(
                            "[SHADOW] HISTORICAL_IGNORED: symbol=%s tf=%s state=%s confluence=%s shadow_start=%s",
                            symbol, timeframe, state_val, event_time_str, self.shadow_started_at,
                        )
                        continue
                    elif state_val == "ARMED":
                        is_bootstrap = True
                        classification = "BOOTSTRAP_EXISTING"
                        _logger.info(
                            "[SHADOW] SHADOW_BOOTSTRAP: BOOTSTRAP_EXISTING setup detectado symbol=%s tf=%s state=%s confluence=%s shadow_start=%s",
                            symbol, timeframe, state_val, event_time_str, self.shadow_started_at,
                        )
                    else:
                        _logger.info(
                            "[SHADOW] HISTORICAL_IGNORED: symbol=%s tf=%s state=%s confluence=%s shadow_start=%s",
                            symbol, timeframe, state_val, event_time_str, self.shadow_started_at,
                        )
                        continue
                else:
                    _logger.info(
                        "[SHADOW] PROSPECTIVE_EVENT: symbol=%s tf=%s state=%s confluence=%s shadow_start=%s",
                        symbol, timeframe, state_val, event_time_str, self.shadow_started_at,
                    )

            evi = EvidencePayload(
                symbol=symbol,
                timeframe=timeframe,
                direction=occ.divergence.direction,
                pivot1={"price": occ.divergence.pivot1.price, "time": str(occ.divergence.pivot1.time)},
                pivot2={"price": occ.divergence.pivot2.price, "time": str(occ.divergence.pivot2.time)},
                rsi1=occ.divergence.pivot1.rsi,
                rsi2=occ.divergence.pivot2.rsi,
                divergence_price_line=(occ.divergence.pivot1.price, occ.divergence.pivot2.price),
                divergence_rsi_line=(occ.divergence.pivot1.rsi, occ.divergence.pivot2.rsi),
                pattern_candle={
                    "name": occ.pattern.pattern_type if occ.pattern else "",
                    "time": str(occ.pattern.candle.time) if occ.pattern else "",
                },
                volume_relative=occ.divergence.candle2.relative_volume,
                activation_level=occ.activation_level,
                entry_price=occ.activation_price or 0.0,
                initial_stop=occ.initial_stop,
                target_price=(
                    occ.activation_level + (2.0 * abs(occ.activation_level - occ.initial_stop))
                    if occ.divergence.direction == "BULLISH"
                    else occ.activation_level - (2.0 * abs(occ.activation_level - occ.initial_stop))
                ),
            )

            # Mapeamento do estado atual
            if is_bootstrap:
                c_state = ShadowState.BOOTSTRAP_EXISTING.value
            elif state_val == "ARMED":
                c_state = ShadowState.ARMED.value
            elif state_val == "ACTIVATED":
                c_state = ShadowState.ACTIVATED.value
            elif state_val == "TARGET_HIT":
                c_state = ShadowState.TARGET_2R.value
            elif state_val == "STOP_HIT":
                c_state = ShadowState.STOPPED.value
            elif state_val == "EXPIRED":
                c_state = ShadowState.EXPIRED.value
            else:
                c_state = ShadowState.INVALIDATED.value

            evt_id = f"evt_{symbol}_{timeframe}_{int(pd.Timestamp(event_time_str).timestamp())}"
            initial_risk = abs(occ.activation_level - occ.initial_stop)
            target_2r = (
                occ.activation_level + (2.0 * initial_risk)
                if occ.divergence.direction == "BULLISH"
                else occ.activation_level - (2.0 * initial_risk)
            )

            evt = ShadowEvent(
                event_id=evt_id,
                candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id,
                candidate_version=HDF_ROBUST_CANDIDATE_V1.candidate_version,
                parameter_hash=HDF_CANDIDATE_V1_PARAMETER_HASH,
                symbol=symbol,
                asset_class=get_asset_class(symbol),
                timeframe=timeframe,
                direction=occ.divergence.direction,
                pattern_type=occ.pattern.pattern_type if occ.pattern else "CONFLUENCE_PATTERN",
                pivot_1_time=str(occ.divergence.pivot1.time),
                pivot_1_price=occ.divergence.pivot1.price,
                pivot_1_rsi=occ.divergence.pivot1.rsi,
                pivot_2_time=str(occ.divergence.pivot2.time),
                pivot_2_price=occ.divergence.pivot2.price,
                pivot_2_rsi=occ.divergence.pivot2.rsi,
                divergence_confirmed_at=event_time_str,
                relative_volume=occ.divergence.candle2.relative_volume,
                confluence_time=event_time_str,
                armed_at=event_time_str if state_val in ("ARMED", "ACTIVATED", "TARGET_HIT", "STOP_HIT") else "",
                activation_level=occ.activation_level,
                activated_at=str(occ.activation_time) if occ.activation_time else "",
                entry_price=occ.activation_price or (
                    occ.activation_level if state_val in ("ACTIVATED", "TARGET_HIT", "STOP_HIT") else 0.0
                ),
                initial_stop=occ.initial_stop,
                target_2R=target_2r,
                initial_risk=initial_risk,
                current_state=c_state,
                market_candle_time=last_closed_time,
                received_at=now_str,
                processed_at=now_str,
                created_at=now_str,
                updated_at=now_str,
                metadata={
                    "synthetic": is_synthetic,
                    "bootstrap_detected": is_bootstrap,
                    "classification": classification,
                    "original_confluence_time": event_time_str,
                },
                evidence=evi.__dict__,
            )

            # Métricas dinâmicas para ativados
            if c_state in (
                ShadowState.ACTIVATED.value, ShadowState.TARGET_2R.value, ShadowState.STOPPED.value
            ):
                act_idx = occ.metadata.get("activation_bar_index")
                if act_idx is not None and act_idx < len(df_closed) - 1:
                    post_df = df_closed.iloc[act_idx + 1 :]
                    evt.bars_since_activation = len(post_df)
                    if not post_df.empty and initial_risk > 0:
                        if occ.divergence.direction == "BULLISH":
                            max_h = post_df["high"].max()
                            min_l = post_df["low"].min()
                            mfe_r = (max_h - evt.entry_price) / initial_risk
                            mae_r = (evt.entry_price - min_l) / initial_risk
                        else:
                            max_h = post_df["high"].max()
                            min_l = post_df["low"].min()
                            mfe_r = (evt.entry_price - min_l) / initial_risk
                            mae_r = (max_h - evt.entry_price) / initial_risk

                        evt.mfe_r_live = round(float(mfe_r), 2)
                        evt.mae_r_live = round(float(mae_r), 2)

                        if mfe_r >= 1.0:
                            evt.milestone_1r_reached = True

            dedup_key = evt.compute_deduplication_key(c_state)
            saved = self.store.save_event(evt, dedup_key=dedup_key)

            if saved:
                if classification == "NEW_PROSPECTIVE_EVENT":
                    self.publisher.publish(
                        ShadowEventType.ENTRY_ACTIVATED if c_state == "ACTIVATED" else ShadowEventType.SETUP_ARMED,
                        evt,
                        {"from_state": "DETECTED", "market_price": evt.activation_level},
                    )
                generated_events.append(evt)
            else:
                self.store.update_event(evt)
                _logger.info(
                    "[SHADOW] DUPLICATE_SKIPPED: symbol=%s tf=%s candle_time=%s dedup_key=%s",
                    symbol, timeframe, last_closed_time, dedup_key,
                )

        # Atualiza scanner_state final
        st.last_processed_candle = last_closed_time
        st.last_scan_at = now_str
        st.scanner_status = ScannerStatus.RUNNING.value
        self.store.save_scanner_state(st)

        return generated_events

    def run_prospective_scan_all(self, data_map: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Varre todas as 39 combinações de mercado a cada ciclo de fechamento de candle."""
        summary = {"processed_combinations": 0, "new_events_count": 0, "errors": 0}

        for sym in SHADOW_ASSETS:
            for tf in SHADOW_TIMEFRAMES:
                key = f"{sym}_{tf}"
                df = data_map.get(key)
                if df is not None and not df.empty:
                    try:
                        evts = self.scan_closed_candle(sym, tf, df)
                        summary["processed_combinations"] += 1
                        summary["new_events_count"] += len(evts)
                    except Exception as ex:
                        summary["errors"] += 1
                        st = self.store.get_scanner_state(
                            HDF_ROBUST_CANDIDATE_V1.candidate_id, sym, tf
                        ) or ShadowScannerState(
                            candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id, symbol=sym, timeframe=tf
                        )
                        st.scanner_status = ScannerStatus.ERROR.value
                        st.error_message = str(ex)
                        self.store.save_scanner_state(st)

        return summary

    def _parse_shadow_started_at(self) -> Optional[datetime]:
        """Parseia shadow_started_at para datetime UTC usando helper centralizado."""
        return parse_utc_timestamp(self.shadow_started_at)

    def _parse_event_time(self, time_str: str) -> Optional[datetime]:
        """Parseia string de tempo de evento para datetime UTC usando helper centralizado."""
        return parse_utc_timestamp(time_str)
