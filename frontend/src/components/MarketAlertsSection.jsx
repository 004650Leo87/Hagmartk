import React, { useEffect, useState } from 'react';
import { getShadowEvents } from '../services/api';

export default function MarketAlertsSection() {
  const [alerts, setAlerts] = useState([]);
  const [filterState, setFilterState] = useState('TODOS');
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [loading, setLoading] = useState(true);

  async function fetchAlerts() {
    try {
      const data = await getShadowEvents();
      setAlerts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Erro ao buscar alertas de mercado:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 4000);
    return () => clearInterval(interval);
  }, []);

  const filteredAlerts = alerts.filter((item) => {
    if (filterState === 'TODOS') return true;
    if (filterState === 'EM FORMAÇÃO') return item.status_code === 'DETECTED' || item.status_code === 'CONFLUENCE_COMPLETE';
    if (filterState === 'ARMADOS') return item.status_code === 'ARMED';
    if (filterState === 'ATIVADOS') return item.status_code === 'ACTIVATED';
    if (filterState === 'FINALIZADOS') return ['TARGET_2R', 'STOPPED', 'EXPIRED', 'INVALIDATED'].includes(item.status_code);
    return true;
  });

  return (
    <div className="market-alerts-wrapper space-y-4">
      {/* Filtros em Português */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '12px' }}>
        <div className="alert-filter-bar">
          {['TODOS', 'EM FORMAÇÃO', 'ARMADOS', 'ATIVADOS', 'FINALIZADOS'].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilterState(f)}
              className={`alert-filter-btn ${filterState === f ? 'active' : ''}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Grid de Cards de Alerta */}
      {loading && alerts.length === 0 ? (
        <div className="text-xs text-slate-400 p-6 text-center bg-slate-900/40 rounded-xl border border-slate-800">
          Carregando análises de mercado em tempo real...
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="text-xs text-slate-400 p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800">
          Nenhuma análise de mercado encontrada para o filtro '{filterState}'.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAlerts.map((alert) => (
            <div
              key={alert.alert_id}
              className="bg-slate-800/90 border border-slate-700/80 hover:border-slate-600 rounded-xl p-4 space-y-3 transition-all shadow-md flex flex-col justify-between"
            >
              <div>
                {/* Header do Card */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="font-bold text-slate-100 text-sm tracking-wide">{alert.title}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-slate-900 text-slate-300 border border-slate-700">
                      SHADOW
                    </span>
                    <span
                      className={`px-2 py-0.5 text-[10px] font-bold rounded ${
                        alert.direction === 'BULLISH'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : 'bg-red-950 text-red-300 border border-red-800'
                      }`}
                    >
                      {alert.direction_label}
                    </span>
                  </div>
                </div>

                {/* Status em Português */}
                <div className="bg-slate-950/80 p-2.5 rounded-lg border border-slate-800 mb-3">
                  <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider block">
                    {alert.status_label}
                  </span>
                  <p className="text-xs text-slate-300 mt-0.5 leading-snug">{alert.description}</p>
                </div>

                {/* Parâmetros do Alerta */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Padrão Confirmado</span>
                    <strong className="text-slate-200">{alert.pattern}</strong>
                  </div>
                  <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Volume Relativo</span>
                    <strong className="text-slate-200">{alert.relative_volume}</strong>
                  </div>
                  <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Nível de Ativação</span>
                    <strong className="text-slate-100 font-mono">{alert.activation_level}</strong>
                  </div>
                  <div className="bg-slate-900/60 p-2 rounded border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Stop Estrutural</span>
                    <strong className="text-red-400 font-mono">{alert.initial_stop}</strong>
                  </div>
                </div>

                {/* Target 2R e MFE se ativado */}
                {alert.target_2R && (
                  <div className="mt-2 bg-emerald-950/30 p-2 rounded border border-emerald-800/40 flex justify-between items-center text-xs">
                    <span className="text-emerald-300 font-medium">Objetivo Observado (2R):</span>
                    <strong className="text-emerald-400 font-mono">{alert.target_2R}</strong>
                  </div>
                )}

                {alert.status_code === 'ACTIVATED' && (
                  <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] bg-slate-950 p-2 rounded border border-slate-800">
                    <div>
                      <span className="text-slate-400">MFE Máximo:</span>{' '}
                      <strong className="text-emerald-400">+{alert.mfe_r_live} R</strong>
                    </div>
                    <div>
                      <span className="text-slate-400">Velas Ativas:</span>{' '}
                      <strong className="text-slate-200">{alert.bars_since_activation}</strong>
                    </div>
                  </div>
                )}
              </div>

              {/* Botão Ver Detalhes */}
              <button
                type="button"
                onClick={() => setSelectedAlert(alert)}
                className="w-full mt-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-semibold rounded transition-colors"
              >
                VER DETALHES TÉCNICOS
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Modal de Detalhes Técnicos do Alerta */}
      {selectedAlert && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 max-w-lg w-full space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h4 className="text-base font-bold text-slate-100">{selectedAlert.title} — Detalhes</h4>
              <button
                type="button"
                onClick={() => setSelectedAlert(null)}
                className="text-slate-400 hover:text-slate-200 text-xl font-bold"
              >
                ×
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-300">
              <div className="bg-slate-950 p-3 rounded border border-slate-800">
                <span className="text-slate-400 block text-[10px] uppercase font-bold">Resumo da Análise</span>
                <strong className="text-emerald-400 text-sm block mt-0.5">{selectedAlert.status_label}</strong>
                <p className="mt-1 text-slate-300">{selectedAlert.description}</p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div><span className="text-slate-400">Candidato ID:</span> <strong className="text-slate-200 block">hdf_dvp_exit_2r</strong></div>
                <div><span className="text-slate-400">Versão:</span> <strong className="text-slate-200 block">1.0.0</strong></div>
                <div><span className="text-slate-400">Timeframe:</span> <strong className="text-slate-200 block">{selectedAlert.timeframe}</strong></div>
                <div><span className="text-slate-400">Padrão Confirmado:</span> <strong className="text-slate-200 block">{selectedAlert.pattern}</strong></div>
              </div>

              <div className="border-t border-slate-800 pt-3">
                <h5 className="font-bold text-slate-200 mb-2">Níveis Estruturais de Preço</h5>
                <div className="space-y-1 font-mono">
                  <div className="flex justify-between"><span>Nível de Ativação:</span> <strong>{selectedAlert.activation_level}</strong></div>
                  <div className="flex justify-between"><span>Stop Estrutural:</span> <strong className="text-red-400">{selectedAlert.initial_stop}</strong></div>
                  <div className="flex justify-between"><span>Alvo de Saída 2R:</span> <strong className="text-emerald-400">{selectedAlert.target_2R}</strong></div>
                </div>
              </div>

              <div className="border-t border-slate-800 pt-2 text-[11px] text-slate-400 flex justify-between">
                <span>Timestamp: {selectedAlert.event_time}</span>
                <span>Watermark: {selectedAlert.symbol} • {selectedAlert.timeframe}</span>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setSelectedAlert(null)}
              className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded"
            >
              FECHAR DETALHES
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
