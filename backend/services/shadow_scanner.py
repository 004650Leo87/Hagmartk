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
    HDFEvidence,
    ScannerStatus,
    ShadowEvent,
    ShadowEventType,
    ShadowScannerState,
    ShadowState,
)
from backend.strategies.hdf.models import ReversalPatternType
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

        st.scan_cycle_count_total += 1

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
            st.scanner_status = ScannerStatus.WAITING_NEW_CANDLE.value
            st.last_scan_at = now_str
            self.store.save_scanner_state(st)
            _logger.debug(
                "[SHADOW] DUPLICATE_SKIPPED: candle %s %s %s já processado",
                symbol, timeframe, last_closed_time,
            )
            return []

        # Novo candle fechado detectado — incrementa contador de avaliações HDF reais
        st.evaluation_count_total += 1
        st.last_evaluated_candle_time = last_closed_time
        st.last_evaluation_at = now_str

        _logger.info(
            "[SHADOW] NEW_CLOSED_CANDLE: symbol=%s tf=%s candle_time=%s scan_time=%s eval_total=%d",
            symbol, timeframe, last_closed_time, now_str, st.evaluation_count_total,
        )

        # Registra telemetria de sucesso na varredura da combinação
        self.store.record_scanner_telemetry(
            HDF_ROBUST_CANDIDATE_V1.candidate_id, symbol, timeframe, success=True, now_str=now_str
        )

        # Registra a observação prospectiva continuada de forma idempotente
        try:
            from backend.services.shadow_observation_engine import ShadowObservationEngine
            obs_engine = ShadowObservationEngine(store=self.store)
            obs_engine.record_observation_cycle(
                symbol=symbol,
                timeframe=timeframe,
                window_time=last_closed_time,
                candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id,
                observed_at=now_str,
            )
        except Exception as _obs_err:
            _logger.warning("[SHADOW] Erro ao gravar observação prospectiva: %s", _obs_err)

        # Avalia a estratégia completa no conjunto de candles (warmup incluso)
        analysis = self.strategy.evaluate_full_dataset_analysis(df_closed, symbol, timeframe)
        occurrences = analysis.get("occurrences", [])

        # Fibonacci research telemetry is isolated from candidate/event promotion.
        try:
            from backend.services.fibonacci_prospective_telemetry import FibonacciProspectiveTelemetryEngine
            fib_engine = FibonacciProspectiveTelemetryEngine(store=self.store)
            fib_engine.process_occurrences(
                symbol=symbol, timeframe=timeframe, df_closed=df_closed,
                occurrences=occurrences, strategy=self.strategy,
                shadow_started_at=self.shadow_started_at,
                candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id,
                is_synthetic=is_synthetic,
            )
        except Exception as _fib_err:
            _logger.warning("[SHADOW] Fibonacci telemetry error: %s", _fib_err)

        # Processa e persiste HDFEvidence para todas as divergências HDF_D (camada de evidência independente)
        self._process_hdf_evidences(symbol, timeframe, df_closed, is_synthetic)

        generated_events: List[ShadowEvent] = []

        for occ in occurrences:
            state_val = occ.state.value

            if state_val not in (
                "ARMED", "ACTIVATED", "TARGET_HIT", "STOP_HIT", "EXPIRED", "INVALIDATED_BEFORE_ACTIVATION"
            ):
                continue

            event_time_str = str(
                getattr(occ, "pivot_2_time", None)
                or getattr(getattr(occ, "temporal_model", None), "confluence_time", "")
                or getattr(occ, "confluence_time", "")
            )
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

            dir_val = getattr(occ, "direction", "BULLISH")
            p1_price = float(getattr(occ, "price_p1", 0.0))
            p1_time = str(getattr(occ, "pivot_1_time", ""))
            p2_price = float(getattr(occ, "price_p2", 0.0))
            p2_time = str(getattr(occ, "pivot_2_time", ""))
            r1_rsi = float(getattr(occ, "rsi_p1", 0.0))
            r2_rsi = float(getattr(occ, "rsi_p2", 0.0))
            act_lvl = float(getattr(occ, "activation_level", 0.0))
            init_stop = float(getattr(occ, "initial_stop", 0.0))
            ent_price = float(getattr(occ, "entry_price", 0.0))

            target_val = (
                act_lvl + (2.0 * abs(act_lvl - init_stop))
                if dir_val == "BULLISH"
                else act_lvl - (2.0 * abs(act_lvl - init_stop))
            )

            evi = EvidencePayload(
                symbol=symbol,
                timeframe=timeframe,
                direction=dir_val,
                pivot1={"price": p1_price, "time": p1_time},
                pivot2={"price": p2_price, "time": p2_time},
                rsi1=r1_rsi,
                rsi2=r2_rsi,
                divergence_price_line=(p1_price, p2_price),
                divergence_rsi_line=(r1_rsi, r2_rsi),
                pattern_candle={
                    "name": getattr(occ, "pattern_type", ""),
                    "time": p2_time,
                },
                volume_relative=float(getattr(occ, "relative_volume", 1.0)),
                activation_level=act_lvl,
                entry_price=ent_price,
                initial_stop=init_stop,
                target_price=target_val,
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

            ts_val = (
                int(pd.Timestamp(event_time_str).timestamp())
                if (event_time_str and event_time_str != "None" and not pd.isna(pd.Timestamp(event_time_str)))
                else int(pd.Timestamp.now(timezone.utc).timestamp())
            )
            evt_id = f"evt_{symbol}_{timeframe}_{ts_val}"
            initial_risk = abs(act_lvl - init_stop)
            target_2r = (
                act_lvl + (2.0 * initial_risk)
                if dir_val == "BULLISH"
                else act_lvl - (2.0 * initial_risk)
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

        # Determina o maior estágio HDF encontrado no ciclo de avaliação
        highest_stage = "NONE"
        for occ in occurrences:
            stg = getattr(occ, "variant_stage", "NONE") or getattr(occ, "state", None)
            if hasattr(stg, "value"):
                stg = stg.value
            stg_str = str(stg)
            if stg_str in ("HDF_DVP", "HDF_DV", "HDF_DP", "HDF_D"):
                highest_stage = stg_str
                break
        st.last_result_stage = highest_stage

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

    def start_auto_scheduler(self, adapter: Any = None, interval_seconds: float = 3.0) -> None:
        """Inicia a thread de fundo autônoma para polling e escaneamento do Shadow Universe."""
        import threading
        import time

        if getattr(self, "_scheduler_running", False):
            return

        self._scheduler_running = True

        def _worker():
            _logger.info("[SHADOW] Scheduler autônomo iniciado (intervalo=%.1fs)", interval_seconds)
            while getattr(self, "_scheduler_running", False):
                try:
                    current_adapter = adapter
                    if current_adapter is None:
                        from backend.engines.market.mt5_market_adapter import MT5MarketAdapter
                        current_adapter = MT5MarketAdapter()

                    try:
                        current_adapter.connect()
                    except Exception:
                        pass

                    import MetaTrader5 as mt5
                    tf_map = {
                        "M15": getattr(mt5, "TIMEFRAME_M15", 15),
                        "H1": getattr(mt5, "TIMEFRAME_H1", 16385),
                        "H4": getattr(mt5, "TIMEFRAME_H4", 16388),
                    }

                    for sym in SHADOW_ASSETS:
                        for tf in SHADOW_TIMEFRAMES:
                            if not getattr(self, "_scheduler_running", False):
                                break
                            tf_const = tf_map.get(tf.upper(), 15)
                            df_candles = pd.DataFrame()
                            try:
                                candles_list = current_adapter.get_candles(sym, tf_const, count=100)
                                if candles_list:
                                    df_candles = pd.DataFrame(candles_list)
                            except Exception as _err:
                                _logger.debug("[SHADOW] Pulo por indisponibilidade/erro em %s %s: %s", sym, tf, _err)

                            try:
                                self.scan_closed_candle(sym, tf, df_candles)
                            except Exception as _scan_err:
                                _logger.warning("[SHADOW] Erro em scan_closed_candle para %s %s: %s", sym, tf, _scan_err)
                except Exception as ex:
                    _logger.warning("[SHADOW] Exceção no loop do scheduler autônomo: %s", ex)

                time.sleep(interval_seconds)

        thread = threading.Thread(target=_worker, daemon=True, name="ShadowAutoScheduler")
        thread.start()

    def stop_auto_scheduler(self) -> None:
        """Para o scheduler autônomo de fundo."""
        self._scheduler_running = False

    def _parse_shadow_started_at(self) -> Optional[datetime]:
        """Parseia shadow_started_at para datetime UTC usando helper centralizado."""
        return parse_utc_timestamp(self.shadow_started_at)

    def _parse_event_time(self, time_str: str) -> Optional[datetime]:
        """Parseia string de tempo de evento para datetime UTC usando helper centralizado."""
        return parse_utc_timestamp(time_str)

    def _process_hdf_evidences(
        self,
        symbol: str,
        timeframe: str,
        df_closed: pd.DataFrame,
        is_synthetic: bool = False,
    ) -> None:
        """Extrai todas as divergências matematicamente confirmadas (HDF_D) e as registra como HDFEvidence."""
        try:
            if df_closed is None or len(df_closed) < self.strategy.minimum_required_bars:
                return

            rsi_series = self.strategy.rsi_indicator.calculate(df_closed)
            df_calc = df_closed.copy()
            df_calc["rsi"] = rsi_series

            pivot_highs, pivot_lows = self.strategy.pivot_detector.find_pivots(df_calc)
            n = len(df_calc)
            asset_class = get_asset_class(symbol)
            now_str = now_utc_str()

            # Bullish check (fundos no preço, fundos no RSI)
            for t in range(self.strategy.minimum_required_bars, n):
                valid_lows = [p for p in pivot_lows if p.confirmed_at_index <= t]
                if len(valid_lows) >= 2:
                    p1, p2 = valid_lows[-2], valid_lows[-1]
                    if p2.confirmed_at_index == t:
                        is_bull, details = self.strategy.div_detector.check_bullish_divergence(p1, p2, rsi_series)
                        if is_bull:
                            vol_curr, vol_ma20, rel_vol, _ = self.strategy.vol_filter.evaluate_volume(df_calc, t)
                            pattern_type, pat_details = self.strategy.pattern_detector.detect_at(df_calc, t)

                            vol_pass = rel_vol >= self.strategy.volume_min_relative
                            pat_pass = pattern_type in (ReversalPatternType.BULLISH_ENGULFING, ReversalPatternType.HAMMER)

                            if vol_pass and pat_pass:
                                stage = "HDF_DVP"
                            elif vol_pass:
                                stage = "HDF_DV"
                            elif pat_pass:
                                stage = "HDF_DP"
                            else:
                                stage = "HDF_D"

                            # Ancoragem visual no fundo real do RSI na janela do pivô
                            p1_win = rsi_series.iloc[max(0, p1.index - self.strategy.pivot_left) : min(len(df_calc), p1.index + self.strategy.pivot_right + 1)]
                            p1_rsi_idx = int(p1_win.idxmin())
                            p1_rsi = float(rsi_series.iloc[p1_rsi_idx])
                            p1_time_str = str(df_calc["time"].iloc[p1_rsi_idx])

                            p2_win = rsi_series.iloc[max(0, p2.index - self.strategy.pivot_left) : min(len(df_calc), p2.index + self.strategy.pivot_right + 1)]
                            p2_rsi_idx = int(p2_win.idxmin())
                            p2_rsi = float(rsi_series.iloc[p2_rsi_idx])
                            p2_time_str = str(df_calc["time"].iloc[p2_rsi_idx])

                            t_clean = p2_time_str.replace(":", "").replace(" ", "_").replace("-", "").replace("+", "").replace("T", "_")
                            ev_id = f"ev_bull_{symbol}_{timeframe}_{t_clean}"
                            pat_str = pattern_type.value if hasattr(pattern_type, "value") else str(pattern_type)
                            source_val = "TEST" if is_synthetic else "LIVE_PROSPECTIVE"

                            # Price integrity validation
                            reasons = []
                            p1_price_val = float(p1.price)
                            p2_price_val = float(p2.price)
                            if p1_price_val <= 0 or p2_price_val <= 0:
                                reasons.append("PRICE_INTEGRITY_FAIL")

                            ev = HDFEvidence(
                                evidence_id=ev_id,
                                symbol=symbol,
                                timeframe=timeframe,
                                asset_class=asset_class,
                                direction="BULLISH",
                                pivot_1_time=p1_time_str,
                                pivot_1_price=p1_price_val,
                                pivot_1_rsi=p1_rsi,
                                pivot_2_time=p2_time_str,
                                pivot_2_price=p2_price_val,
                                pivot_2_rsi=p2_rsi,
                                divergence_confirmed=True,
                                relative_volume=float(rel_vol),
                                volume_pass=vol_pass,
                                pattern_type=pat_str,
                                pattern_pass=pat_pass,
                                pattern_policy="SAME_BAR",
                                variant_stage=stage,
                                candidate_created=stage == "HDF_DVP",
                                armed=stage == "HDF_DVP",
                                reason_codes=reasons,
                                source=source_val,
                                is_test=is_synthetic,
                                detected_at=str(p2.confirmed_at_time),
                                created_at=now_str,
                            )
                            self.store.save_hdf_evidence(ev)

            # Bearish check (topos no preço, topos no RSI)
            for t in range(self.strategy.minimum_required_bars, n):
                valid_highs = [p for p in pivot_highs if p.confirmed_at_index <= t]
                if len(valid_highs) >= 2:
                    p1, p2 = valid_highs[-2], valid_highs[-1]
                    if p2.confirmed_at_index == t:
                        is_bear, details = self.strategy.div_detector.check_bearish_divergence(p1, p2, rsi_series)
                        if is_bear:
                            vol_curr, vol_ma20, rel_vol, _ = self.strategy.vol_filter.evaluate_volume(df_calc, t)
                            pattern_type, pat_details = self.strategy.pattern_detector.detect_at(df_calc, t)

                            vol_pass = rel_vol >= self.strategy.volume_min_relative
                            pat_pass = pattern_type in (ReversalPatternType.BEARISH_ENGULFING, ReversalPatternType.SHOOTING_STAR)

                            if vol_pass and pat_pass:
                                stage = "HDF_DVP"
                            elif vol_pass:
                                stage = "HDF_DV"
                            elif pat_pass:
                                stage = "HDF_DP"
                            else:
                                stage = "HDF_D"

                            # Ancoragem visual no topo real do RSI na janela do pivô
                            p1_win = rsi_series.iloc[max(0, p1.index - self.strategy.pivot_left) : min(len(df_calc), p1.index + self.strategy.pivot_right + 1)]
                            p1_rsi_idx = int(p1_win.idxmax())
                            p1_rsi = float(rsi_series.iloc[p1_rsi_idx])
                            p1_time_str = str(df_calc["time"].iloc[p1_rsi_idx])

                            p2_win = rsi_series.iloc[max(0, p2.index - self.strategy.pivot_left) : min(len(df_calc), p2.index + self.strategy.pivot_right + 1)]
                            p2_rsi_idx = int(p2_win.idxmax())
                            p2_rsi = float(rsi_series.iloc[p2_rsi_idx])
                            p2_time_str = str(df_calc["time"].iloc[p2_rsi_idx])

                            t_clean = p2_time_str.replace(":", "").replace(" ", "_").replace("-", "").replace("+", "").replace("T", "_")
                            ev_id = f"ev_bear_{symbol}_{timeframe}_{t_clean}"
                            pat_str = pattern_type.value if hasattr(pattern_type, "value") else str(pattern_type)
                            source_val = "TEST" if is_synthetic else "LIVE_PROSPECTIVE"

                            # Price integrity validation
                            reasons = []
                            p1_price_val = float(p1.price)
                            p2_price_val = float(p2.price)
                            if p1_price_val <= 0 or p2_price_val <= 0:
                                reasons.append("PRICE_INTEGRITY_FAIL")

                            ev = HDFEvidence(
                                evidence_id=ev_id,
                                symbol=symbol,
                                timeframe=timeframe,
                                asset_class=asset_class,
                                direction="BEARISH",
                                pivot_1_time=p1_time_str,
                                pivot_1_price=p1_price_val,
                                pivot_1_rsi=p1_rsi,
                                pivot_2_time=p2_time_str,
                                pivot_2_price=p2_price_val,
                                pivot_2_rsi=p2_rsi,
                                divergence_confirmed=True,
                                relative_volume=float(rel_vol),
                                volume_pass=vol_pass,
                                pattern_type=pat_str,
                                pattern_pass=pat_pass,
                                pattern_policy="SAME_BAR",
                                variant_stage=stage,
                                candidate_created=stage == "HDF_DVP",
                                armed=stage == "HDF_DVP",
                                reason_codes=reasons,
                                source=source_val,
                                is_test=is_synthetic,
                                detected_at=str(p2.confirmed_at_time),
                                created_at=now_str,
                            )
                            self.store.save_hdf_evidence(ev)
        except Exception as err:
            _logger.warning("[SHADOW] Erro ao extrair HDFEvidence: %s", err)
