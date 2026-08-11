import React, { useState, useEffect, useMemo } from 'react';
import {
  disableShadowCandidate,
  enableShadowCandidate,
  getCompletedShadowHistory,
  getShadowCandidates,
  getShadowEvidence,
  getShadowForwardValidation,
  getShadowIntelligence,
  getShadowObservationDrilldown,
  getShadowObservationHealth,
  getShadowObservationProgress,
  getShadowScanners,
  getShadowStatisticalValidation,
  getShadowStatistics,
  getShadowStatus,
  getShadowTelemetry,
} from "../services/api";

const STATUS_CLASS = {
  RUNNING: "shadow-monitor-status-running",
  ERROR: "shadow-monitor-status-error",
  WAITING_NEW_CANDLE: "shadow-monitor-status-waiting",
  DISABLED: "shadow-monitor-status-disabled",
};

const STATUS_LABELS = {
  RUNNING: "● ATIVO",
  ERROR: "✕ ERRO",
  WAITING_NEW_CANDLE: "◎ AGUARDANDO",
  DISABLED: "○ DESATIVADO",
};

const FOREX = ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD","EURJPY","GBPJPY"];
const METALS = ["XAUUSD","XAGUSD"];

function getAssetClass(symbol) {
  if (FOREX.includes(symbol)) return "FOREX";
  if (METALS.includes(symbol)) return "METALS";
  return "CRYPTO";
}

export default function ShadowStrategiesView() {
  const [candidates, setCandidates] = useState([]);
  const [status, setStatus] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [scanners, setScanners] = useState([]);
  const [history, setHistory] = useState([]);
  const [forwardVal, setForwardVal] = useState(null);
  const [statVal, setStatVal] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [intel, setIntel] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [obsHealth, setObsHealth] = useState(null);
  const [obsProgress, setObsProgress] = useState(null);
  const [selectedDrilldown, setSelectedDrilldown] = useState(null);
  const [loadingDrilldown, setLoadingDrilldown] = useState(false);
  const [obsSearch, setObsSearch] = useState("");
  const [obsFilterTf, setObsFilterTf] = useState("TODOS");
  const [showTelemetryModal, setShowTelemetryModal] = useState(false);
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);
  const [breakdownTab, setBreakdownTab] = useState("symbol");
  const [showQualityDetails, setShowQualityDetails] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");

  const [monitorSearch, setMonitorSearch] = useState("");
  const [monitorAssetFilter, setMonitorAssetFilter] = useState("TODOS");
  const [monitorTfFilter, setMonitorTfFilter] = useState("TODOS");
  const [monitorStatusFilter, setMonitorStatusFilter] = useState("TODOS");

  const [showParams, setShowParams] = useState(false);

  const candidate = candidates[0] || null;
  const isEnabled = status?.enabled ?? true;

  async function loadData() {
    setLoading(true);
    try {
      const [candsRes, statusRes, statsRes, scannersRes, histRes, fwdRes, statRes, telemRes, intelRes, evRes, obsHRes, obsPRes] = await Promise.allSettled([
        getShadowCandidates(),
        getShadowStatus(),
        getShadowStatistics(),
        getShadowScanners(),
        getCompletedShadowHistory(),
        getShadowForwardValidation(),
        getShadowStatisticalValidation(),
        getShadowTelemetry(),
        getShadowIntelligence(),
        getShadowEvidence(),
        getShadowObservationHealth(),
        getShadowObservationProgress(),
      ]);
      if (candsRes.status === "fulfilled") setCandidates(candsRes.value);
      if (statusRes.status === "fulfilled") setStatus(statusRes.value);
      if (statsRes.status === "fulfilled") setStatistics(statsRes.value);
      if (scannersRes.status === "fulfilled") setScanners(scannersRes.value);
      if (histRes.status === "fulfilled") setHistory(histRes.value);
      if (fwdRes.status === "fulfilled") setForwardVal(fwdRes.value);
      if (statRes.status === "fulfilled") setStatVal(statRes.value);
      if (telemRes.status === "fulfilled") setTelemetry(telemRes.value);
      if (intelRes.status === "fulfilled") setIntel(intelRes.value);
      if (evRes.status === "fulfilled") setEvidence(evRes.value);
      if (obsHRes.status === "fulfilled") setObsHealth(obsHRes.value);
      if (obsPRes.status === "fulfilled") setObsProgress(obsPRes.value);
      setError("");
    } catch {
      setError("Erro ao carregar dados do Shadow Mode.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 5000);
    return () => clearInterval(iv);
  }, []);

  async function handleToggleShadow() {
    if (!candidate) return;
    setActionLoading(true);
    try {
      if (isEnabled) {
        await disableShadowCandidate(candidate.candidate_id);
      } else {
        await enableShadowCandidate(candidate.candidate_id);
      }
      await loadData();
    } catch (err) {
      alert("Falha ao alterar estado do Shadow Mode: " + err.message);
    } finally {
      setActionLoading(false);
    }
  }

  const filteredScanners = useMemo(() => {
    return scanners.filter((sc) => {
      const q = monitorSearch.trim().toUpperCase();
      if (q && !sc.symbol.includes(q)) return false;
      if (monitorAssetFilter === "FOREX" && !FOREX.includes(sc.symbol)) return false;
      if (monitorAssetFilter === "METAIS" && !METALS.includes(sc.symbol)) return false;
      if (monitorAssetFilter === "CRIPTO" && FOREX.includes(sc.symbol)) return false;
      if (monitorAssetFilter === "CRIPTO" && METALS.includes(sc.symbol)) return false;
      if (monitorTfFilter !== "TODOS" && sc.timeframe !== monitorTfFilter) return false;
      if (monitorStatusFilter !== "TODOS" && sc.status !== monitorStatusFilter) return false;
      return true;
    });
  }, [scanners, monitorSearch, monitorAssetFilter, monitorTfFilter, monitorStatusFilter]);

  const activeScannersCount = scanners.filter((s) => s.status === "RUNNING").length;
  const errorScannersCount = scanners.filter((s) => s.status === "ERROR").length;

  if (loading && !candidate) {
    return <div className="p-6 text-gray-400">Carregando candidato HDF e estatísticas do Shadow Mode...</div>;
  }

  return (
    <div className="strategy-dashboard">
      {error && <div className="drawer-message error">{error}</div>}

      <div className="strategy-hero-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: '800', color: '#34d399', margin: 0 }}>Hagmartk Divergence Flow</h2>
              <span className="badge badge-candidate">
                {candidate?.research_status || "ROBUST_CANDIDATE"}
              </span>
              <span className="badge badge-version">
                v{candidate?.candidate_version || "1.0.0"}
              </span>
            </div>
            <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px', marginBottom: 0 }}>
              Estratégia de divergência quantitativa RSI/Volume aprovada no Stage 2 Deep Robustness.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: '#0b1320', padding: '8px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '10px', color: '#64748b', display: 'block', fontWeight: '600' }}>SHADOW MODE</span>
              <strong style={{ fontSize: '12px', color: isEnabled ? '#34d399' : '#64748b' }}>
                {isEnabled ? "● ATIVO (PROSPECTIVO)" : "○ DESATIVADO"}
              </strong>
            </div>
            <button
              type="button"
              disabled={actionLoading}
              onClick={handleToggleShadow}
              className={`indicator-add-btn ${isEnabled ? '' : 'disabled'}`}
              style={{ background: isEnabled ? '#10b981' : '#334155', fontSize: '11px', padding: '6px 12px' }}
            >
              {actionLoading ? "Processando..." : isEnabled ? "DESATIVAR SHADOW" : "ATIVAR SHADOW"}
            </button>
          </div>
        </div>

        <div className="strategy-metrics-grid">
          <div className="strategy-metric-box">
            <span className="strategy-metric-label">Classificação</span>
            <strong style={{ color: '#f59e0b' }}>{candidate?.research_status || "ROBUST_CANDIDATE"}</strong>
          </div>
          <div className="strategy-metric-box">
            <span className="strategy-metric-label">Política de Saída</span>
            <strong style={{ color: '#34d399' }}>{candidate?.exit_policy || "EXIT_2R"} (2.0 Target)</strong>
          </div>
          <div className="strategy-metric-box">
            <span className="strategy-metric-label">Live Broker Trading</span>
            <strong style={{ color: '#ef4444' }}>OFF (SEGURANÇA)</strong>
          </div>
          <div className="strategy-metric-box">
            <span className="strategy-metric-label">Publicação Externa</span>
            <strong style={{ color: '#64748b' }}>OFF (INTERNO)</strong>
          </div>
        </div>

        <div style={{ marginTop: '14px', paddingTop: '10px', borderTop: '1px solid #1e293b' }}>
          <button
            type="button"
            onClick={() => setShowParams((p) => !p)}
            className="indicator-preset-btn"
            title="Parâmetros congelados (Somente leitura)"
            style={{ fontSize: '11px', padding: '4px 10px' }}
          >
            {showParams ? '▲ Parâmetros' : '▼ Parâmetros'}
          </button>

          {showParams && (
            <div style={{ marginTop: '10px', background: '#070d17', padding: '12px', borderRadius: '8px', border: '1px solid #1e293b' }}>
              <div className="strategy-metrics-grid">
                {[
                  ["RSI Method", "Wilder (14)"],
                  ["Pivôs (Esq/Dir)", "2 / 2"],
                  ["Distância Pivôs", "5 – 50 velas"],
                  ["Volume Relativo", "≥ 1.0x"],
                  ["Ativação", "NEXT_BAR (≤5 velas)"],
                  ["Stop / Target", "Estrutural / 2.0R"],
                ].map(([label, value]) => (
                  <div key={label} className="strategy-metric-box">
                    <span className="strategy-metric-label">{label}</span>
                    <strong style={{ color: '#f1f5f9' }}>{value}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="alert-filter-bar" style={{ marginBottom: '12px' }}>
        {[
          { id: "overview", label: "Visão Geral" },
          { id: "forward_val", label: "Validação Prospectiva (Forward)" },
          { id: "scanners", label: `Shadow Monitor (${scanners.length}/39)` },
          { id: "statistics", label: "Estatísticas Prospectivas vs Histórico" },
          { id: "history", label: "Histórico Prospectivo" },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`alert-filter-btn ${activeTab === tab.id ? "active" : ""}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <div className="strategy-hero-card" style={{ gap: '12px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: '700', color: '#f8fafc', margin: '0 0 8px 0' }}>
            Status do Scanner Prospectivo HDF V1
          </h3>

          <div className="strategy-metrics-grid">
            {[
              { label: "Ativos Monitorados", value: "13", sub: "Shadow Universe" },
              { label: "Timeframes", value: "3", sub: "M15 · H1 · H4" },
              { label: "Combinações", value: "39", sub: "13 × 3 TF" },
              { label: "Scanners Ativos", value: activeScannersCount, sub: `de ${scanners.length} total`, color: activeScannersCount > 0 ? "#34d399" : "#64748b" },
              { label: "Com Erro", value: errorScannersCount, sub: "scanners", color: errorScannersCount > 0 ? "#f87171" : "#64748b" },
              { label: "Eventos Ativos", value: status?.active_events ?? 0, sub: "Armados + Ativados", color: "#f59e0b" },
            ].map((m) => (
              <div key={m.label} className="strategy-metric-box">
                <span className="strategy-metric-label">{m.label}</span>
                <strong style={{ fontSize: '18px', color: m.color || "#f1f5f9" }}>{m.value}</strong>
                <span style={{ fontSize: '10px', color: '#64748b', display: 'block', marginTop: '2px' }}>{m.sub}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '12px', background: '#070d17', padding: '10px 14px', borderRadius: '8px', border: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px' }}>
            <span style={{ color: '#64748b' }}>Início da Coleta Prospectiva (UTC):</span>
            <strong style={{ color: '#34d399' }}>{status?.started_at || "Em aguardo"}</strong>
          </div>
        </div>
      )}

      {activeTab === "scanners" && (
        <div className="bg-slate-800/60 p-5 rounded-xl border border-slate-700/60 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            {[
              { label: "Total Combinações", value: "39", color: "" },
              { label: "Scanners Ativos", value: `${activeScannersCount}/39`, color: activeScannersCount > 0 ? "text-emerald-400" : "text-slate-500" },
              { label: "Com Erro", value: errorScannersCount, color: errorScannersCount > 0 ? "text-red-400" : "" },
              { label: "Eventos Ativos", value: status?.active_events ?? 0, color: "text-amber-400" },
            ].map((m) => (
              <div key={m.label} className="bg-slate-900 p-3 rounded border border-slate-700">
                <span className="text-slate-400 block">{m.label}</span>
                <strong className={`text-lg ${m.color || "text-slate-100"}`}>{m.value}</strong>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <input
              type="text"
              id="shadow-monitor-search"
              placeholder="Buscar ativo..."
              value={monitorSearch}
              onChange={(e) => setMonitorSearch(e.target.value)}
              className="watchlist-search-input"
              style={{ maxWidth: "160px" }}
            />
            <div className="shadow-monitor-filter-bar" style={{ margin: 0 }}>
              {["TODOS", "FOREX", "METAIS", "CRIPTO"].map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`shadow-monitor-filter-btn ${monitorAssetFilter === f ? "active" : ""}`}
                  onClick={() => setMonitorAssetFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>
            <div className="shadow-monitor-filter-bar" style={{ margin: 0 }}>
              {["TODOS", "M15", "H1", "H4"].map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`shadow-monitor-filter-btn ${monitorTfFilter === f ? "active" : ""}`}
                  onClick={() => setMonitorTfFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>
            <div className="shadow-monitor-filter-bar" style={{ margin: 0 }}>
              {["TODOS", "RUNNING", "ERROR"].map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`shadow-monitor-filter-btn ${monitorStatusFilter === f ? "active" : ""}`}
                  onClick={() => setMonitorStatusFilter(f)}
                >
                  {f}
                </button>
              ))}
            </div>
            <span className="text-xs text-slate-500 ml-auto">
              {filteredScanners.length} de {scanners.length}
            </span>
          </div>

          <div style={{ maxHeight: "420px", overflowY: "auto", border: "1px solid #1e293b", borderRadius: "8px" }}>
            <table className="shadow-monitor-table">
              <thead style={{ background: "#0f172a", position: "sticky", top: 0, zIndex: 1 }}>
                <tr>
                  <th>ATIVO</th>
                  <th>CLASSE</th>
                  <th>TIMEFRAME</th>
                  <th>STATUS SCANNER</th>
                  <th>ÚLTIMO CANDLE</th>
                  <th>ÚLTIMA VERIFICAÇÃO</th>
                  <th>ERRO</th>
                </tr>
              </thead>
              <tbody>
                {filteredScanners.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", color: "#475569", padding: "24px" }}>
                      Nenhuma combinação para os filtros selecionados.
                    </td>
                  </tr>
                ) : (
                  filteredScanners.map((sc, idx) => {
                    const cls = getAssetClass(sc.symbol);
                    const clsColor = cls === "FOREX" ? { bg: "rgba(99,102,241,0.15)", fg: "#a5b4fc" }
                      : cls === "METALS" ? { bg: "rgba(245,158,11,0.15)", fg: "#fcd34d" }
                      : { bg: "rgba(16,185,129,0.15)", fg: "#6ee7b7" };
                    return (
                      <tr key={`${sc.symbol}_${sc.timeframe}_${idx}`}>
                        <td style={{ fontWeight: 700, color: "#e2e8f0", fontFamily: "monospace" }}>{sc.symbol}</td>
                        <td>
                          <span style={{ padding: "2px 6px", borderRadius: "4px", fontSize: "10px", fontWeight: 700, background: clsColor.bg, color: clsColor.fg }}>
                            {cls}
                          </span>
                        </td>
                        <td>
                          <span style={{ padding: "2px 7px", borderRadius: "4px", background: "#1e293b", border: "1px solid #334155", fontSize: "11px", fontWeight: 700 }}>
                            {sc.timeframe}
                          </span>
                        </td>
                        <td className={STATUS_CLASS[sc.status] || ""} style={{ fontSize: "11px" }}>
                          {STATUS_LABELS[sc.status] || sc.status}
                        </td>
                        <td style={{ fontFamily: "monospace", fontSize: "11px", color: "#94a3b8" }}>
                          {sc.last_processed_candle ? sc.last_processed_candle.slice(0, 16) : <span style={{ color: "#475569" }}>Aguardando</span>}
                        </td>
                        <td style={{ fontFamily: "monospace", fontSize: "11px", color: "#64748b" }}>
                          {sc.last_scan_at ? sc.last_scan_at.slice(0, 16) : "--"}
                        </td>
                        <td style={{ fontSize: "10px", color: "#f87171", maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {sc.error_message || "—"}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          {errorScannersCount > 0 && (
            <div style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "8px", padding: "12px", fontSize: "12px", color: "#fca5a5" }}>
              ⚠ {errorScannersCount} scanner(s) com erro. Verifique a conectividade com o MetaTrader 5.
            </div>
          )}
        </div>
      )}

      {activeTab === "statistics" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-slate-800/80 p-5 rounded-xl border border-slate-700 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-bold text-slate-200 text-sm uppercase tracking-wider">Pesquisa Histórica (Stage 2 Reference)</h4>
                <span className="text-[11px] bg-blue-900/40 text-blue-300 border border-blue-700/50 px-2 py-0.5 rounded font-medium">390.000 Candles Históricos</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                {[
                  { label: "Profit Factor (PF)", value: "1.25", color: "text-emerald-400" },
                  { label: "Expectancy em R", value: "+0.12 R / trade", color: "text-emerald-400" },
                  { label: "Net R Líquido", value: "+49.24 R", color: "" },
                  { label: "Max Drawdown (R)", value: "17.15 R", color: "" },
                ].map((m) => (
                  <div key={m.label} className="bg-slate-900 p-3 rounded border border-slate-800">
                    <span className="text-slate-400 block">{m.label}</span>
                    <strong className={`text-xl ${m.color || "text-slate-100"}`}>{m.value}</strong>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-slate-400 italic">* Amostra histórica auditada. Nunca misturada com eventos em tempo real.</p>
            </div>
            <div className="bg-slate-800/80 p-5 rounded-xl border border-emerald-500/30 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-bold text-emerald-400 text-sm uppercase tracking-wider">Shadow Prospectivo (Live Tracking)</h4>
                <span className="text-[11px] bg-emerald-900/40 text-emerald-300 border border-emerald-700/50 px-2 py-0.5 rounded font-medium">Amostra ZERADA</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                {[
                  { label: "Profit Factor Shadow", value: statistics?.profit_factor_shadow?.toFixed(2) || "0.00", color: "text-emerald-400" },
                  { label: "Expectancy Shadow", value: `${statistics?.expectancy_r_shadow?.toFixed(2) || "0.00"} R`, color: "text-emerald-400" },
                  { label: "Net R Prospectivo", value: `${statistics?.net_r_shadow?.toFixed(2) || "0.00"} R`, color: "" },
                  { label: "Trades Finalizados", value: (statistics?.targets_reached_count || 0) + (statistics?.stops_reached_count || 0), color: "" },
                ].map((m) => (
                  <div key={m.label} className="bg-slate-900 p-3 rounded border border-slate-800">
                    <span className="text-slate-400 block">{m.label}</span>
                    <strong className={`text-xl ${m.color || "text-slate-100"}`}>{m.value}</strong>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-slate-400 italic">* Registra exclusivamente análises a partir de {statistics?.shadow_started_at || "agora"}.</p>
            </div>
          </div>
        </div>
      )}

      {activeTab === "history" && (
        <div className="bg-slate-800/60 p-5 rounded-xl border border-slate-700/60 space-y-3">
          <h3 className="font-bold text-slate-100 text-sm uppercase tracking-wider">
            Histórico Prospectivo de Eventos Finalizados ({history.length})
          </h3>
          {history.length === 0 ? (
            <div className="text-xs text-slate-400 py-6 text-center bg-slate-900/40 rounded-lg">
              Nenhum evento prospectivo finalizado ainda. O scanner monitoriza 39 combinações continuamente.
            </div>
          ) : (
            <div style={{ maxHeight: "400px", overflowY: "auto", border: "1px solid #1e293b", borderRadius: "8px" }}>
              <table className="shadow-monitor-table">
                <thead style={{ background: "#0f172a", position: "sticky", top: 0 }}>
                  <tr>
                    <th>Título / Ativo</th>
                    <th>Direção</th>
                    <th>Padrão</th>
                    <th>Ativação</th>
                    <th>Stop</th>
                    <th>Target 2R</th>
                    <th>Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={h.alert_id || i}>
                      <td style={{ fontWeight: 700 }}>{h.title}</td>
                      <td>
                        <span style={{ padding: "2px 7px", borderRadius: "4px", fontSize: "10px", fontWeight: 700, background: h.direction === "BULLISH" ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)", color: h.direction === "BULLISH" ? "#34d399" : "#f87171" }}>
                          {h.direction_label}
                        </span>
                      </td>
                      <td style={{ color: "#94a3b8" }}>{h.pattern}</td>
                      <td style={{ fontFamily: "monospace", fontSize: "11px" }}>{h.activation_level}</td>
                      <td style={{ fontFamily: "monospace", fontSize: "11px", color: "#f87171" }}>{h.initial_stop}</td>
                      <td style={{ fontFamily: "monospace", fontSize: "11px", color: "#34d399" }}>{h.target_2R}</td>
                      <td style={{ fontWeight: 600 }}>{h.status_label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === "forward_val" && (
        <div className="strategy-hero-card" style={{ gap: "16px" }}>
          {/* Header da Validação Prospectiva */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", borderBottom: "1px solid #1e293b", paddingBottom: "12px" }}>
            <div>
              <h3 style={{ fontSize: "16px", fontWeight: "800", color: "#34d399", margin: 0 }}>
                MOTOR DE VALIDAÇÃO PROSPECTIVA — SHADOW MODE V1
              </h3>
              <p style={{ fontSize: "11px", color: "#94a3b8", margin: "4px 0 0 0" }}>
                Acompanhamento em tempo real do candidato HDF em mercado prospectivo não visto no histórico.
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", background: "#0b1320", padding: "6px 12px", borderRadius: "6px", border: "1px solid #1e293b" }}>
              <span style={{ fontSize: "10px", color: "#64748b", fontWeight: "600" }}>STATUS DA AMOSTRA:</span>
              <strong style={{ fontSize: "11px", color: forwardVal?.terminal_trades_count > 0 ? "#34d399" : "#f59e0b" }}>
                {forwardVal?.sample_status === "NO_TERMINAL_TRADES" ? "SEM TRADES TERMINAIS" : "OBSERVAÇÃO PROSPECTIVA"}
              </strong>
            </div>
          </div>

          {/* Cards Principais de Métricas Financeiras (R) */}
          <div className="strategy-metrics-grid">
            <div className="strategy-metric-box">
              <span className="strategy-metric-label">Trades Concluídos</span>
              <strong style={{ color: "#f8fafc", fontSize: "16px" }}>{forwardVal?.terminal_trades_count ?? 0}</strong>
            </div>
            <div className="strategy-metric-box">
              <span className="strategy-metric-label">Win Rate</span>
              <strong style={{ color: forwardVal?.win_rate != null ? (forwardVal.win_rate >= 37.89 ? "#34d399" : "#f59e0b") : "#64748b" }}>
                {forwardVal?.win_rate != null ? `${forwardVal.win_rate}%` : "Sem amostra"}
              </strong>
            </div>
            <div className="strategy-metric-box">
              <span className="strategy-metric-label">Expectancy (R)</span>
              <strong style={{ color: forwardVal?.expectancy_r != null ? (forwardVal.expectancy_r > 0 ? "#34d399" : "#ef4444") : "#64748b" }}>
                {forwardVal?.expectancy_r != null ? `${forwardVal.expectancy_r > 0 ? "+" : ""}${forwardVal.expectancy_r}R` : "Sem amostra"}
              </strong>
            </div>
            <div className="strategy-metric-box">
              <span className="strategy-metric-label">Profit Factor</span>
              <strong style={{ color: forwardVal?.profit_factor != null ? (forwardVal.profit_factor >= 1.0 ? "#34d399" : "#ef4444") : "#64748b" }}>
                {forwardVal?.profit_factor != null ? forwardVal.profit_factor : (forwardVal?.profit_factor_flag === "NO_LOSSES_YET" ? "100% Wins" : "Sem amostra")}
              </strong>
            </div>
            <div className="strategy-metric-box">
              <span className="strategy-metric-label">Total R Acumulado</span>
              <strong style={{ color: forwardVal?.total_r != null ? (forwardVal.total_r > 0 ? "#34d399" : "#ef4444") : "#64748b" }}>
                {forwardVal?.total_r != null ? `${forwardVal.total_r > 0 ? "+" : ""}${forwardVal.total_r}R` : "Sem amostra"}
              </strong>
            </div>
            <div className="strategy-metric-box">
              <span className="strategy-metric-label">Max Drawdown (R)</span>
              <strong style={{ color: forwardVal?.max_drawdown_r != null ? "#f87171" : "#64748b" }}>
                {forwardVal?.max_drawdown_r != null ? `${forwardVal.max_drawdown_r}R` : "Sem amostra"}
              </strong>
            </div>
          </div>

          {/* Seção de Evidência Estatística da Amostra Viva (95% CI) */}
          <div style={{ background: "#0b1320", padding: "14px", borderRadius: "8px", border: "1px solid #1e293b" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "10px" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#f8fafc", margin: 0 }}>
                EVIDÊNCIA ESTATÍSTICA DA AMOSTRA VIVA (INTERVALOS 95% CI)
              </h4>
              <span className="badge" style={{ background: "rgba(96,165,250,0.15)", color: "#60a5fa", borderColor: "#3b82f6" }}>
                REQUISITO: REVISÃO HUMANA OBRIGATÓRIA
              </span>
            </div>

            <div className="strategy-metrics-grid">
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Estado de Evidência</span>
                <strong style={{ color: statVal?.statistical_evidence?.evidence_state === "POSITIVE_EDGE_EVIDENCE" ? "#34d399" : (statVal?.statistical_evidence?.evidence_state === "NEGATIVE_EDGE_EVIDENCE" ? "#ef4444" : "#f59e0b"), fontSize: "12px" }}>
                  {statVal?.statistical_evidence?.evidence_state || "NOT_EVALUATED"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Expectancy R (95% t-Student CI)</span>
                <strong style={{ color: "#f8fafc", fontSize: "12px" }}>
                  {statVal?.statistical_evidence?.expectancy_ci_95?.[0] != null ? `${statVal.statistical_evidence.expectancy_ci_95[0]}R → ${statVal.statistical_evidence.expectancy_ci_95[1]}R` : "Inconclusivo"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Win Rate (95% Wilson Score CI)</span>
                <strong style={{ color: "#f8fafc", fontSize: "12px" }}>
                  {statVal?.statistical_evidence?.win_rate_ci_95?.[0] != null ? `${statVal.statistical_evidence.win_rate_ci_95[0]}% → ${statVal.statistical_evidence.win_rate_ci_95[1]}%` : "Inconclusivo"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Precisão Estatística (Largura IC)</span>
                <strong style={{ color: "#60a5fa", fontSize: "12px" }}>
                  {statVal?.statistical_evidence?.precision_level || "VERY_LOW"} {statVal?.statistical_evidence?.ci_width_r != null ? `(${statVal.statistical_evidence.ci_width_r}R)` : ""}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Maturidade Operacional</span>
                <strong style={{ color: "#f8fafc", fontSize: "12px" }}>
                  {statVal?.operational_policy?.maturity_stage || "STAGE_1_INITIAL"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Cobertura de Scanner</span>
                <strong style={{ color: statVal?.measurement?.scanner_coverage != null ? "#34d399" : "#94a3b8", fontSize: "11px" }}>
                  {statVal?.measurement?.scanner_coverage != null ? `${(statVal.measurement.scanner_coverage * 100).toFixed(0)}%` : "INDISPONÍVEL (Ainda sem telemetria)"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Decisão & Ação</span>
                <strong style={{ color: "#f59e0b", fontSize: "11px" }}>
                  {statVal?.decision?.state || "CONTINUE_OBSERVING"} (Aprovação Humana Necessária)
                </strong>
              </div>
            </div>

            {/* Avisos e Reason Codes */}
            {statVal?.decision?.state === "HUMAN_REVIEW_POSITIVE" && (
              <div style={{ marginTop: "10px", background: "rgba(16,185,129,0.1)", border: "1px solid #10b981", borderRadius: "6px", padding: "8px 12px", color: "#34d399", fontSize: "11px" }}>
                ✓ <strong>Evidência estatística positiva detectada.</strong> Revisão humana necessária para avaliar promoção.
              </div>
            )}
            {statVal?.decision?.state === "HUMAN_REVIEW_NEGATIVE" && (
              <div style={{ marginTop: "10px", background: "rgba(239,68,68,0.1)", border: "1px solid #ef4444", borderRadius: "6px", padding: "8px 12px", color: "#f87171", fontSize: "11px" }}>
                ⚠ <strong>Evidência estatística desfavorável detectada.</strong> Revisão humana necessária para avaliar suspensão.
              </div>
            )}
          </div>

          {/* Seção de Observabilidade Operacional (Saúde do Shadow) */}
          <div style={{ background: "#0b1320", padding: "14px", borderRadius: "8px", border: "1px solid #1e293b" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "10px" }}>
              <div>
                <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#f8fafc", margin: 0 }}>
                  SAÚDE DO SHADOW (OBSERVABILIDADE OPERACIONAL V1)
                </h4>
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                  Métricas de infraestrutura de varredura (não associadas a lucro/desempenho da estratégia)
                </span>
              </div>
              <button
                type="button"
                className="btn secondary"
                style={{ fontSize: "11px", padding: "4px 10px" }}
                onClick={() => setShowTelemetryModal(true)}
              >
                📊 Ver Detalhes (39 Combinações)
              </button>
            </div>

            <div className="strategy-metrics-grid">
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Status da Infraestrutura</span>
                <strong style={{
                  color: telemetry?.global?.health === "HEALTHY" ? "#34d399" : (telemetry?.global?.health === "DEGRADED" ? "#f59e0b" : (telemetry?.global?.health === "UNAVAILABLE" ? "#ef4444" : "#94a3b8")),
                  fontSize: "12px"
                }}>
                  ● {telemetry?.global?.health || "UNKNOWN"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Cobertura Acumulada</span>
                <strong style={{ color: "#f8fafc", fontSize: "12px" }}>
                  {telemetry?.global?.coverage != null ? `${(telemetry.global.coverage * 100).toFixed(1)}%` : "INDISPONÍVEL (Sem amostragem)"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Checks Executados / Esperados</span>
                <strong style={{ color: "#f8fafc", fontSize: "12px" }}>
                  {telemetry?.global?.successful_checks ?? 0} / {telemetry?.global?.expected_checks ?? 0}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Falhas de Varredura</span>
                <strong style={{ color: telemetry?.global?.failed_checks > 0 ? "#ef4444" : "#34d399", fontSize: "12px" }}>
                  {telemetry?.global?.failed_checks ?? 0}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Última Varredura Registrada</span>
                <strong style={{ color: "#60a5fa", fontSize: "11px" }}>
                  {telemetry?.global?.last_activity_at ? new Date(telemetry.global.last_activity_at).toLocaleTimeString("pt-BR") : "--"}
                </strong>
              </div>
            </div>
          </div>

          {/* Modal / Drawer de Detalhes das 39 Combinações */}
          {showTelemetryModal && (
            <div style={{
              position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
              background: "rgba(0,0,0,0.8)", zIndex: 9999, display: "flex",
              alignItems: "center", justifyContent: "center", padding: "20px"
            }}>
              <div style={{
                background: "#0f172a", border: "1px solid #334155", borderRadius: "10px",
                width: "900px", maxWidth: "95vw", maxHeight: "85vh", display: "flex",
                flexDirection: "column", padding: "20px"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div>
                    <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#f8fafc", margin: 0 }}>
                      TELEMETRIA DAS 39 COMBINAÇÕES DO SHADOW UNIVERSE
                    </h3>
                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                      Monitoramento individual por Instrumento x Timeframe
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn secondary"
                    onClick={() => setShowTelemetryModal(false)}
                    style={{ padding: "4px 12px", fontSize: "12px" }}
                  >
                    Fechar ✕
                  </button>
                </div>

                <div style={{ overflowY: "auto", flex: 1, border: "1px solid #1e293b", borderRadius: "6px" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                    <thead>
                      <tr style={{ background: "#1e293b", color: "#94a3b8" }}>
                        <th style={{ padding: "10px" }}>Ativo</th>
                        <th style={{ padding: "10px" }}>Classe</th>
                        <th style={{ padding: "10px" }}>TF</th>
                        <th style={{ padding: "10px" }}>Status</th>
                        <th style={{ padding: "10px" }}>Cobertura</th>
                        <th style={{ padding: "10px" }}>Sucesso / Esperados</th>
                        <th style={{ padding: "10px" }}>Falhas</th>
                        <th style={{ padding: "10px" }}>Último Check</th>
                      </tr>
                    </thead>
                    <tbody>
                      {telemetry?.combinations?.map((c) => (
                        <tr key={`${c.symbol}-${c.timeframe}`} style={{ borderBottom: "1px solid #1e293b", color: "#f8fafc" }}>
                          <td style={{ padding: "8px 10px", fontWeight: "700" }}>{c.symbol}</td>
                          <td style={{ padding: "8px 10px", color: "#94a3b8" }}>{c.asset_class}</td>
                          <td style={{ padding: "8px 10px" }}>{c.timeframe}</td>
                          <td style={{ padding: "8px 10px", color: c.health === "HEALTHY" ? "#34d399" : (c.health === "DEGRADED" ? "#f59e0b" : "#ef4444") }}>
                            ● {c.health}
                          </td>
                          <td style={{ padding: "8px 10px" }}>
                            {c.coverage != null ? `${(c.coverage * 100).toFixed(1)}%` : "INDISPONÍVEL"}
                          </td>
                          <td style={{ padding: "8px 10px" }}>{c.successful_checks} / {c.expected_checks}</td>
                          <td style={{ padding: "8px 10px", color: c.failed_checks > 0 ? "#ef4444" : "#94a3b8" }}>{c.failed_checks}</td>
                          <td style={{ padding: "8px 10px", color: "#94a3b8", fontSize: "11px" }}>
                            {c.last_success_at ? c.last_success_at.slice(11, 19) : "--"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Funil de Conversão de Oportunidades */}
          <div style={{ background: "#0b1320", padding: "14px", borderRadius: "8px", border: "1px solid #1e293b" }}>
            <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#f8fafc", margin: "0 0 10px 0" }}>
              Funil de Conversão (Oportunidades → Ativações → Conclusões)
            </h4>
            <div className="strategy-metrics-grid">
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">1. Oportunidades Elegíveis</span>
                <strong style={{ color: "#60a5fa" }}>{forwardVal?.prospective_opportunities ?? 0}</strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">2. Taxa de Ativação</span>
                <strong style={{ color: "#f59e0b" }}>
                  {forwardVal?.activation_rate != null ? `${forwardVal.activation_rate}%` : "0%"} ({forwardVal?.activated_count ?? 0})
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">3. Trades Terminais</span>
                <strong style={{ color: "#34d399" }}>{forwardVal?.terminal_trades_count ?? 0}</strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">4. Wins / Losses</span>
                <strong style={{ color: "#f8fafc" }}>
                  <span style={{ color: "#34d399" }}>{forwardVal?.wins_count ?? 0}W</span> / <span style={{ color: "#ef4444" }}>{forwardVal?.losses_count ?? 0}L</span>
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Expirados sem Ativação</span>
                <strong style={{ color: "#64748b" }}>{forwardVal?.expired_pre_activation_count ?? 0}</strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Invalidados sem Ativação</span>
                <strong style={{ color: "#64748b" }}>{forwardVal?.invalidated_pre_activation_count ?? 0}</strong>
              </div>
            </div>
          </div>

          {/* Seção de Inteligência Prospectiva (Maturidade da Amostra & Comparação Coerente) */}
          <div style={{ background: "#0b1320", padding: "14px", borderRadius: "8px", border: "1px solid #1e293b" }}>
            <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#f8fafc", margin: "0 0 10px 0" }}>
              INTELIGÊNCIA E VALIDAÇÃO PROSPECTIVA V1
            </h4>

            <div className="strategy-metrics-grid">
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Status do Tamanho da Amostra</span>
                <strong style={{ color: intel?.sample_size?.status === "MATURE" ? "#34d399" : (intel?.sample_size?.status === "USABLE" ? "#60a5fa" : (intel?.sample_size?.status === "EARLY" ? "#f59e0b" : "#94a3b8")), fontSize: "12px" }}>
                  ● {intel?.sample_size?.status || "INSUFFICIENT"} ({intel?.sample_size?.terminal_trades_count ?? 0} trades)
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Coerência Histórica (Estatística)</span>
                <strong style={{ color: intel?.historical_comparison?.status === "CONSISTENT" ? "#34d399" : (intel?.historical_comparison?.status === "WATCH" ? "#f59e0b" : (intel?.historical_comparison?.status === "DIVERGING" ? "#ef4444" : "#94a3b8")), fontSize: "12px" }}>
                  ● {intel?.historical_comparison?.status || "INSUFFICIENT_DATA"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Contexto de Qualidade dos Dados</span>
                <strong style={{ color: intel?.data_quality?.quality_context === "VALID" ? "#34d399" : (intel?.data_quality?.quality_context === "PARTIAL" ? "#f59e0b" : "#ef4444"), fontSize: "12px" }}>
                  ● {intel?.data_quality?.quality_context || "UNAVAILABLE"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Distribuição Long / Short</span>
                <strong style={{ color: "#f8fafc", fontSize: "11px" }}>
                  <span style={{ color: "#34d399" }}>🔺 {intel?.prospective_performance?.structural?.long_ratio_pct ?? 0}%</span> / <span style={{ color: "#ef4444" }}>🔻 {intel?.prospective_performance?.structural?.short_ratio_pct ?? 0}%</span>
                </strong>
              </div>
            </div>

            {intel?.historical_comparison?.reason && (
              <div style={{ marginTop: "10px", fontSize: "11px", color: "#94a3b8", background: "rgba(30,41,59,0.5)", padding: "6px 10px", borderRadius: "4px" }}>
                ℹ <strong>Parecer de Coerência:</strong> {intel.historical_comparison.reason}
              </div>
            )}
          </div>

          {/* Seção da Decision & Evidence Layer V1 (Julgamento Observacional READ-ONLY) */}
          <div style={{ background: "#0b1320", padding: "14px", borderRadius: "8px", border: "1px solid #1e293b" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "10px" }}>
              <div>
                <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#f8fafc", margin: 0 }}>
                  CAMADA DE JULGAMENTO QUANTITATIVO OBSERVACIONAL V1
                </h4>
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                  Classificação determinística da força da evidência (READ-ONLY • Sem tomadas de ação automáticas)
                </span>
              </div>
              <button
                type="button"
                className="btn secondary"
                style={{ fontSize: "11px", padding: "4px 10px" }}
                onClick={() => setShowEvidenceModal(true)}
              >
                💬 Por que? (Explicações Detalhadas)
              </button>
            </div>

            <div className="strategy-metrics-grid">
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Status Observacional</span>
                <strong style={{
                  color: evidence?.observational_status === "EVIDENCE_CONSISTENT" ? "#34d399" : (evidence?.observational_status === "VALIDATING" ? "#60a5fa" : (evidence?.observational_status === "EARLY_VALIDATION" ? "#f59e0b" : (evidence?.observational_status === "EVIDENCE_DIVERGING" || evidence?.observational_status === "DATA_QUALITY_WARNING" ? "#ef4444" : "#94a3b8"))),
                  fontSize: "12px"
                }}>
                  ● {evidence?.observational_status || "COLLECTING_DATA"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Estado de Evidência</span>
                <strong style={{
                  color: evidence?.evidence_state === "ROBUST_EVIDENCE" ? "#34d399" : (evidence?.evidence_state === "DEVELOPING_EVIDENCE" ? "#60a5fa" : (evidence?.evidence_state === "EARLY_EVIDENCE" ? "#f59e0b" : (evidence?.evidence_state === "DEGRADED_EVIDENCE" ? "#ef4444" : "#94a3b8"))),
                  fontSize: "12px"
                }}>
                  ● {evidence?.evidence_state || "INSUFFICIENT_EVIDENCE"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Expectativa IC 95%</span>
                <strong style={{ color: "#f8fafc", fontSize: "11px" }}>
                  {evidence?.performance?.ci_lower != null ? `[${evidence.performance.ci_lower > 0 ? "+" : ""}${evidence.performance.ci_lower}R, ${evidence.performance.ci_upper > 0 ? "+" : ""}${evidence.performance.ci_upper}R]` : "Amostra Insuficiente"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Reason Codes Ativos</span>
                <strong style={{ color: "#60a5fa", fontSize: "12px" }}>
                  {evidence?.reason_codes ? `${evidence.reason_codes.length} regras ativas` : "--"}
                </strong>
              </div>
            </div>

            {evidence?.contradictions && evidence.contradictions.length > 0 && (
              <div style={{ marginTop: "10px", background: "rgba(239,68,68,0.1)", border: "1px solid #ef4444", borderRadius: "6px", padding: "8px 12px", color: "#f87171", fontSize: "11px" }}>
                ⚠ <strong>Contradições Detectadas:</strong> {evidence.contradictions.join(" • ")}
              </div>
            )}
          </div>

          {/* Modal / Drawer de Explicações Detalhadas em Linguagem Humana */}
          {showEvidenceModal && (
            <div style={{
              position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
              background: "rgba(0,0,0,0.8)", zIndex: 9999, display: "flex",
              alignItems: "center", justifyContent: "center", padding: "20px"
            }}>
              <div style={{
                background: "#0f172a", border: "1px solid #334155", borderRadius: "10px",
                width: "750px", maxWidth: "95vw", maxHeight: "85vh", display: "flex",
                flexDirection: "column", padding: "20px"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div>
                    <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#f8fafc", margin: 0 }}>
                      PARECER QUANTITATIVO & REASON CODES — SHADOW MODE
                    </h3>
                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                      Tradução determinística em linguagem clara da força da evidência observada
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn secondary"
                    onClick={() => setShowEvidenceModal(false)}
                    style={{ padding: "4px 12px", fontSize: "12px" }}
                  >
                    Fechar ✕
                  </button>
                </div>

                <div style={{ overflowY: "auto", flex: 1, border: "1px solid #1e293b", borderRadius: "6px", padding: "14px", background: "#070d17" }}>
                  <h4 style={{ fontSize: "12px", fontWeight: "700", color: "#60a5fa", marginTop: 0, marginBottom: "10px" }}>
                    REASON CODES & JUSTIFICATIVAS OPERACIONAIS
                  </h4>
                  <ul style={{ margin: 0, paddingLeft: "18px", color: "#f8fafc", fontSize: "12px", display: "flex", flexDirection: "column", gap: "10px" }}>
                    {evidence?.human_reasons?.map((reason, idx) => (
                      <li key={idx}>
                        <strong>{evidence.reason_codes[idx]}:</strong> {reason}
                      </li>
                    ))}
                  </ul>

                  {evidence?.contradictions && evidence.contradictions.length > 0 && (
                    <div style={{ marginTop: "16px" }}>
                      <h4 style={{ fontSize: "12px", fontWeight: "700", color: "#f87171", marginBottom: "8px" }}>
                        ANÁLISE DE CONTRADIÇÕES E ADVERTÊNCIAS
                      </h4>
                      <ul style={{ margin: 0, paddingLeft: "18px", color: "#f87171", fontSize: "11px" }}>
                        {evidence.contradictions.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Seção de Observação Prospectiva & Acumulação Continuada (Fase 4F) */}
          <div style={{ background: "#0b1320", padding: "14px", borderRadius: "8px", border: "1px solid #1e293b" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "12px" }}>
              <div>
                <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#f8fafc", margin: 0 }}>
                  OBSERVAÇÃO PROSPECTIVA & ACUMULAÇÃO CONTINUADA (39 COMBINAÇÕES)
                </h4>
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                  Acompanhamento continuado do crescimento real da amostra e saúde da observação sem look-ahead bias
                </span>
              </div>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <input
                  type="text"
                  placeholder="Buscar ativo/TF..."
                  value={obsSearch}
                  onChange={(e) => setObsSearch(e.target.value)}
                  style={{ background: "#0f172a", border: "1px solid #334155", color: "#f8fafc", padding: "4px 8px", borderRadius: "4px", fontSize: "11px", width: "120px" }}
                />
                <select
                  value={obsFilterTf}
                  onChange={(e) => setObsFilterTf(e.target.value)}
                  style={{ background: "#0f172a", border: "1px solid #334155", color: "#f8fafc", padding: "4px 8px", borderRadius: "4px", fontSize: "11px" }}
                >
                  <option value="TODOS">Todos TFs</option>
                  <option value="M15">M15</option>
                  <option value="H1">H1</option>
                  <option value="H4">H4</option>
                </select>
              </div>
            </div>

            {/* Cabeçalho Resumo de Saúde */}
            <div className="strategy-metrics-grid" style={{ marginBottom: "12px" }}>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Universo Shadow</span>
                <strong style={{ color: "#f8fafc", fontSize: "12px" }}>
                  {obsHealth?.total_universe_combinations ?? 39} combinações
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Observadas</span>
                <strong style={{ color: "#34d399", fontSize: "12px" }}>
                  {obsHealth?.observed_combinations ?? 0} / 39
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Saudáveis</span>
                <strong style={{ color: "#34d399", fontSize: "12px" }}>
                  {obsHealth?.healthy_combinations ?? 0}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Degradadas / Aguardando</span>
                <strong style={{ color: obsHealth?.degraded_combinations > 0 ? "#ef4444" : "#94a3b8", fontSize: "12px" }}>
                  {obsHealth?.degraded_combinations ?? 0} deg / {obsHealth?.insufficient_data_combinations ?? 39} aguard
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Cobertura Global</span>
                <strong style={{ color: (obsHealth?.global_coverage_pct ?? 0) >= 95 ? "#34d399" : "#f59e0b", fontSize: "12px" }}>
                  {obsHealth?.global_coverage_pct != null ? `${obsHealth.global_coverage_pct.toFixed(1)}%` : "Indisponível"}
                </strong>
              </div>
              <div className="strategy-metric-box">
                <span className="strategy-metric-label">Última Atualização</span>
                <strong style={{ color: "#60a5fa", fontSize: "11px" }}>
                  {obsHealth?.newest_observation_at ? new Date(obsHealth.newest_observation_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : "Acumulando..."}
                </strong>
              </div>
            </div>

            {/* Tabela de Acúmulo por Combinação */}
            <div style={{ overflowX: "auto", border: "1px solid #1e293b", borderRadius: "6px" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px", textAlign: "left", color: "#f8fafc" }}>
                <thead>
                  <tr style={{ background: "#0f172a", borderBottom: "1px solid #1e293b", color: "#94a3b8" }}>
                    <th style={{ padding: "8px 10px" }}>Ativo</th>
                    <th style={{ padding: "8px 10px" }}>TF</th>
                    <th style={{ padding: "8px 10px" }}>Observações</th>
                    <th style={{ padding: "8px 10px" }}>Eventos HDF</th>
                    <th style={{ padding: "8px 10px" }}>Amostra (Resolvidos)</th>
                    <th style={{ padding: "8px 10px" }}>Cobertura</th>
                    <th style={{ padding: "8px 10px" }}>Estado de Evidência</th>
                    <th style={{ padding: "8px 10px" }}>Saúde</th>
                    <th style={{ padding: "8px 10px", textAlign: "right" }}>Ação</th>
                  </tr>
                </thead>
                <tbody>
                  {obsProgress?.combinations
                    ?.filter((c) => {
                      if (obsFilterTf !== "TODOS" && c.timeframe !== obsFilterTf) return false;
                      if (obsSearch && !c.symbol.toLowerCase().includes(obsSearch.toLowerCase())) return false;
                      return true;
                    })
                    .slice(0, 15)
                    .map((c, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid #1e293b", background: i % 2 === 0 ? "#070d17" : "#0b1320" }}>
                        <td style={{ padding: "6px 10px", fontWeight: "700" }}>{c.symbol}</td>
                        <td style={{ padding: "6px 10px", color: "#60a5fa" }}>{c.timeframe}</td>
                        <td style={{ padding: "6px 10px" }}>{c.observations_count}</td>
                        <td style={{ padding: "6px 10px" }}>{c.hdf_events_count}</td>
                        <td style={{ padding: "6px 10px", fontWeight: "700" }}>{c.sample_size}</td>
                        <td style={{ padding: "6px 10px", color: c.coverage_pct >= 95 ? "#34d399" : (c.coverage_pct > 0 ? "#f59e0b" : "#94a3b8") }}>
                          {c.coverage_pct != null ? `${c.coverage_pct.toFixed(1)}%` : "N/D"}
                        </td>
                        <td style={{ padding: "6px 10px", color: c.current_evidence_state === "ROBUST_EVIDENCE" ? "#34d399" : (c.current_evidence_state === "DEVELOPING_EVIDENCE" ? "#60a5fa" : "#f59e0b") }}>
                          {c.current_evidence_state}
                        </td>
                        <td style={{ padding: "6px 10px" }}>
                          <span style={{
                            padding: "2px 6px", borderRadius: "4px", fontSize: "10px", fontWeight: "700",
                            background: c.health === "HEALTHY" ? "rgba(52,211,153,0.15)" : (c.health === "DEGRADED" ? "rgba(245,158,11,0.15)" : "rgba(148,163,184,0.15)"),
                            color: c.health === "HEALTHY" ? "#34d399" : (c.health === "DEGRADED" ? "#f59e0b" : "#94a3b8"),
                          }}>
                            {c.health}
                          </span>
                        </td>
                        <td style={{ padding: "6px 10px", textAlign: "right" }}>
                          <button
                            type="button"
                            className="btn secondary"
                            style={{ padding: "2px 8px", fontSize: "10px" }}
                            onClick={async () => {
                              setLoadingDrilldown(true);
                              try {
                                const data = await getShadowObservationDrilldown(c.symbol, c.timeframe);
                                setSelectedDrilldown(data);
                              } catch {
                                setSelectedDrilldown(null);
                              } finally {
                                setLoadingDrilldown(false);
                              }
                            }}
                          >
                            Drill-down →
                          </button>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Modal de Drill-Down por Combinação (Fase 4F) */}
          {(selectedDrilldown || loadingDrilldown) && (
            <div style={{
              position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
              background: "rgba(0,0,0,0.8)", zIndex: 9999, display: "flex",
              alignItems: "center", justifyContent: "center", padding: "20px"
            }}>
              <div style={{
                background: "#0f172a", border: "1px solid #334155", borderRadius: "10px",
                width: "800px", maxWidth: "95vw", maxHeight: "85vh", display: "flex",
                flexDirection: "column", padding: "20px"
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div>
                    <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#f8fafc", margin: 0 }}>
                      DRILL-DOWN PROSPECTIVO — {selectedDrilldown ? `${selectedDrilldown.symbol} (${selectedDrilldown.timeframe})` : "Carregando..."}
                    </h3>
                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                      Histórico detalhado de observações, eventos e transições de estado de evidência
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn secondary"
                    onClick={() => setSelectedDrilldown(null)}
                    style={{ padding: "4px 12px", fontSize: "12px" }}
                  >
                    Fechar ✕
                  </button>
                </div>

                {loadingDrilldown ? (
                  <div style={{ padding: "40px", textAlign: "center", color: "#94a3b8" }}>Carregando dados de drill-down...</div>
                ) : (
                  <div style={{ overflowY: "auto", flex: 1, border: "1px solid #1e293b", borderRadius: "6px", padding: "14px", background: "#070d17" }}>
                    <div className="strategy-metrics-grid" style={{ marginBottom: "16px" }}>
                      <div className="strategy-metric-box">
                        <span className="strategy-metric-label">Observações Gravadas</span>
                        <strong style={{ color: "#f8fafc", fontSize: "12px" }}>{selectedDrilldown?.observations_count ?? 0}</strong>
                      </div>
                      <div className="strategy-metric-box">
                        <span className="strategy-metric-label">Eventos HDF</span>
                        <strong style={{ color: "#60a5fa", fontSize: "12px" }}>{selectedDrilldown?.events_count ?? 0}</strong>
                      </div>
                      <div className="strategy-metric-box">
                        <span className="strategy-metric-label">Estado de Evidência Atual</span>
                        <strong style={{ color: "#34d399", fontSize: "12px" }}>
                          {selectedDrilldown?.latest_observation?.evidence_state || "INSUFFICIENT_EVIDENCE"}
                        </strong>
                      </div>
                      <div className="strategy-metric-box">
                        <span className="strategy-metric-label">Status Observacional</span>
                        <strong style={{ color: "#60a5fa", fontSize: "12px" }}>
                          {selectedDrilldown?.latest_observation?.observational_status || "COLLECTING_DATA"}
                        </strong>
                      </div>
                    </div>

                    <h4 style={{ fontSize: "12px", fontWeight: "700", color: "#60a5fa", marginBottom: "8px" }}>
                      HISTÓRICO DE TRANSIÇÕES DE ESTADO DE EVIDÊNCIA
                    </h4>
                    {selectedDrilldown?.evidence_transitions && selectedDrilldown.evidence_transitions.length > 0 ? (
                      <ul style={{ margin: 0, paddingLeft: "18px", color: "#f8fafc", fontSize: "11px", marginBottom: "16px" }}>
                        {selectedDrilldown.evidence_transitions.map((t, idx) => (
                          <li key={idx}>
                            <strong>{t.transitioned_at}:</strong> Transição de <code>{t.from_state}</code> → <code>{t.to_state}</code> ({t.reason_code})
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div style={{ color: "#94a3b8", fontSize: "11px", marginBottom: "16px" }}>Nenhuma transição de estado gravada até o momento.</div>
                    )}

                    <h4 style={{ fontSize: "12px", fontWeight: "700", color: "#60a5fa", marginBottom: "8px" }}>
                      ÚLTIMAS OBSERVAÇÕES REGISTRADAS
                    </h4>
                    {selectedDrilldown?.observation_history && selectedDrilldown.observation_history.length > 0 ? (
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "10px", textAlign: "left", color: "#f8fafc" }}>
                        <thead>
                          <tr style={{ background: "#0f172a", borderBottom: "1px solid #1e293b", color: "#94a3b8" }}>
                            <th style={{ padding: "4px 8px" }}>Candle/Window</th>
                            <th style={{ padding: "4px 8px" }}>Status</th>
                            <th style={{ padding: "4px 8px" }}>Evidência</th>
                            <th style={{ padding: "4px 8px" }}>Sample</th>
                            <th style={{ padding: "4px 8px" }}>Cobertura</th>
                            <th style={{ padding: "4px 8px" }}>Gravado em</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedDrilldown.observation_history.slice(0, 5).map((o, idx) => (
                            <tr key={idx} style={{ borderBottom: "1px solid #1e293b" }}>
                              <td style={{ padding: "4px 8px" }}>{o.window_time}</td>
                              <td style={{ padding: "4px 8px" }}>{o.observational_status}</td>
                              <td style={{ padding: "4px 8px" }}>{o.evidence_state}</td>
                              <td style={{ padding: "4px 8px" }}>{o.sample_size}</td>
                              <td style={{ padding: "4px 8px" }}>{o.scanner_coverage != null ? `${(o.scanner_coverage * 100).toFixed(1)}%` : "N/D"}</td>
                              <td style={{ padding: "4px 8px", color: "#94a3b8" }}>{o.observed_at}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <div style={{ color: "#94a3b8", fontSize: "11px" }}>Nenhuma observação no banco.</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
            <div style={{ background: "#070d17", padding: "14px", borderRadius: "8px", border: "1px solid #1e293b" }}>
              <span className="badge badge-candidate" style={{ marginBottom: "8px", display: "inline-block" }}>
                REFERÊNCIA HISTÓRICA CONGELADA
              </span>
              <div style={{ fontSize: "11px", color: "#94a3b8", display: "flex", flexDirection: "column", gap: "6px", marginTop: "8px" }}>
                <div><strong>Amostra:</strong> 417 trades (Stage 2 Deep Robustness)</div>
                <div><strong>Total R:</strong> +49.24R</div>
                <div><strong>Win Rate:</strong> 37.89%</div>
                <div><strong>Profit Factor:</strong> 1.25</div>
                <div><strong>Payoff:</strong> 2.0</div>
                <div><strong>Monte Carlo Pass:</strong> 99.8%</div>
              </div>
            </div>

            <div style={{ background: "#070d17", padding: "14px", borderRadius: "8px", border: "1px solid #10b981" }}>
              <span className="badge badge-version" style={{ background: "rgba(16,185,129,0.15)", color: "#34d399", borderColor: "#10b981", marginBottom: "8px", display: "inline-block" }}>
                SHADOW MODE PROSPECTIVO (LIVE)
              </span>
              <div style={{ fontSize: "11px", color: "#94a3b8", display: "flex", flexDirection: "column", gap: "6px", marginTop: "8px" }}>
                <div><strong>Amostra:</strong> {forwardVal?.terminal_trades_count ?? 0} trades concluídos</div>
                <div><strong>Total R:</strong> {forwardVal?.total_r != null ? `${forwardVal.total_r}R` : "Sem amostra"}</div>
                <div><strong>Win Rate:</strong> {forwardVal?.win_rate != null ? `${forwardVal.win_rate}%` : "Sem amostra"}</div>
                <div><strong>Profit Factor:</strong> {forwardVal?.profit_factor != null ? forwardVal.profit_factor : "Sem amostra"}</div>
                <div><strong>Status:</strong> {forwardVal?.sample_status === "NO_TERMINAL_TRADES" ? "Aguardando execuções do Shadow" : "Em observação"}</div>
                <div><strong>Ambiguidades Same-Bar:</strong> {forwardVal?.same_bar_ambiguous_count ?? 0}</div>
              </div>
            </div>
          </div>

          {/* Breakdowns por Grupo */}
          <div style={{ background: "#0b1320", padding: "14px", borderRadius: "8px", border: "1px solid #1e293b" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px", marginBottom: "10px" }}>
              <h4 style={{ fontSize: "13px", fontWeight: "700", color: "#f8fafc", margin: 0 }}>
                Breakdown Prospectivo por Subgrupo
              </h4>
              <div className="evidence-drawer-filters">
                {[
                  { id: "symbol", label: "Por Ativo" },
                  { id: "timeframe", label: "Por Timeframe" },
                  { id: "direction", label: "Por Direção" },
                  { id: "asset_class", label: "Por Classe" },
                ].map((bTab) => (
                  <button
                    key={bTab.id}
                    type="button"
                    className={`evidence-filter-btn ${breakdownTab === bTab.id ? "active" : ""}`}
                    onClick={() => setBreakdownTab(bTab.id)}
                  >
                    {bTab.label}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ maxHeight: "250px", overflowY: "auto" }}>
              <table className="shadow-monitor-table">
                <thead>
                  <tr>
                    <th>Subgrupo</th>
                    <th>Oportunidades</th>
                    <th>Ativações</th>
                    <th>Trades Terminais</th>
                    <th>Wins / Losses</th>
                    <th>Win Rate</th>
                    <th>Total R</th>
                  </tr>
                </thead>
                <tbody>
                  {(forwardVal?.breakdowns?.[breakdownTab] || []).length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", color: "#64748b", padding: "12px" }}>
                        Nenhum registro prospectivo para este subgrupo ainda.
                      </td>
                    </tr>
                  ) : (
                    (forwardVal?.breakdowns?.[breakdownTab] || []).map((row, idx) => (
                      <tr key={row.key || idx}>
                        <td style={{ fontWeight: 700, color: "#f8fafc" }}>{row.key}</td>
                        <td>{row.opportunities}</td>
                        <td>{row.activations}</td>
                        <td>{row.terminal_trades}</td>
                        <td>
                          <span style={{ color: "#34d399" }}>{row.wins}W</span> / <span style={{ color: "#ef4444" }}>{row.losses}L</span>
                        </td>
                        <td>{row.win_rate != null ? `${row.win_rate}%` : "—"}</td>
                        <td style={{ fontWeight: 700, color: row.total_r > 0 ? "#34d399" : (row.total_r < 0 ? "#ef4444" : "#94a3b8") }}>
                          {row.total_r > 0 ? "+" : ""}{row.total_r}R
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Qualidade da Amostra & Observação */}
          <div style={{ borderTop: "1px solid #1e293b", paddingTop: "10px" }}>
            <button
              type="button"
              className="indicator-preset-btn"
              onClick={() => setShowQualityDetails((p) => !p)}
              style={{ fontSize: "11px" }}
            >
              {showQualityDetails ? "▲ Ocultar Qualidade da Amostra" : "▼ Qualidade da Amostra & Transparência"}
            </button>

            {showQualityDetails && (
              <div style={{ marginTop: "10px", background: "#070d17", padding: "12px", borderRadius: "8px", border: "1px solid #1e293b", fontSize: "11px", color: "#94a3b8" }}>
                <div><strong>Eventos de Bootstrap Descartados da Performance:</strong> {forwardVal?.bootstrap_existing_count ?? 0}</div>
                <div><strong>Eventos com Ambiguidade de Mesma Barra (Stop-First):</strong> {forwardVal?.same_bar_ambiguous_count ?? 0}</div>
                <div><strong>Data Quality Warnings:</strong> {(forwardVal?.data_quality_warnings || []).length === 0 ? "Zero avisos" : forwardVal?.data_quality_warnings.join(", ")}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
