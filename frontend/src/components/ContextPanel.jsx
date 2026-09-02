import React, { useState } from 'react';

export default function ContextPanel({
  mode = 'watchlist', // 'watchlist' | 'evidence' | 'shadow' | 'settings' | 'system'
  onSelectMode,
  onClose,
  watchlist = [],
  selectedSymbol,
  onSelectSymbol,
  onRemoveFromWatchlist,
  onAddToWatchlistClick,
  evidenceData,
  shadowData,
  indicators,
  onToggleIndicator,
  systemStatus = 'UNKNOWN',
  systemHealth = null,
  operationalCount = 33,
  totalCount = 39,
}) {
  const [watchlistFilter, setWatchlistFilter] = useState('');

  const safeWatchlist = Array.isArray(watchlist) ? watchlist : [];

  const filteredWatchlist = safeWatchlist.filter((item) => {
    const sym = typeof item === 'string' ? item : item?.symbol;
    return sym ? sym.toLowerCase().includes((watchlistFilter || '').toLowerCase()) : false;
  });

  return (
    <aside className="hk-context-panel">
      <div className="hk-context-header">
        <div className="hk-context-tabs" style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`hk-pill-btn ${mode === 'watchlist' ? 'active' : ''}`}
            onClick={() => onSelectMode && onSelectMode('watchlist')}
            style={{ fontSize: '10px', padding: '3px 7px' }}
          >
            📋 Watchlist
          </button>
          <button
            type="button"
            className={`hk-pill-btn ${mode === 'evidence' ? 'active' : ''}`}
            onClick={() => onSelectMode && onSelectMode('evidence')}
            style={{ fontSize: '10px', padding: '3px 7px' }}
          >
            ⚡ Evidência
          </button>
          <button
            type="button"
            className={`hk-pill-btn ${mode === 'system' ? 'active' : ''}`}
            onClick={() => onSelectMode && onSelectMode('system')}
            style={{ fontSize: '10px', padding: '3px 7px' }}
          >
            🖥️ Sistema
          </button>
        </div>
        <button type="button" className="hk-close-btn" onClick={onClose} title="Fechar Painel MFD">
          ×
        </button>
      </div>

      <div className="hk-context-body">
        {/* MODE 1: WATCHLIST (COMPACT FINANCIAL TERMINAL ROWS) */}
        {mode === 'watchlist' && (
          <div className="hk-watchlist-container">
            <div className="hk-watchlist-controls">
              <input
                type="text"
                className="hk-search-input"
                placeholder="Filtrar símbolo..."
                value={watchlistFilter}
                onChange={(e) => setWatchlistFilter(e.target.value)}
              />
              <button
                type="button"
                className="hk-add-symbol-btn"
                onClick={onAddToWatchlistClick}
                title="Adicionar Ativo do Catálogo MT5"
              >
                +
              </button>
            </div>

            <div className="hk-wl-table-header notranslate">
              <span className="notranslate">ATIVO</span>
              <span className="notranslate">BID</span>
              <span className="notranslate">ASK</span>
              <span className="notranslate">SPREAD</span>
              <span></span>
            </div>

            <div className="hk-watchlist-list">
              {filteredWatchlist.length === 0 ? (
                <div className="hk-empty-state">Nenhum ativo encontrado na watchlist.</div>
              ) : (
                filteredWatchlist.map((item, idx) => {
                  const sym = typeof item === 'string' ? item : (item?.symbol || `SYM-${idx}`);
                  const isSelected = sym === selectedSymbol;
                  const spreadVal = typeof item === 'object' && item !== null ? (item.spread_points || item.spread || 0) : 0;
                  const bid = typeof item === 'object' && item !== null && item.bid !== null && item.bid !== undefined ? item.bid : '--';
                  const ask = typeof item === 'object' && item !== null && item.ask !== null && item.ask !== undefined ? item.ask : '--';

                  return (
                    <div
                      key={sym}
                      className={`hk-wl-row ${isSelected ? 'selected' : ''}`}
                      onClick={() => onSelectSymbol && onSelectSymbol(sym)}
                    >
                      <span className="hk-wl-col-sym">{sym}</span>
                      <span className="hk-wl-col-bid">{bid}</span>
                      <span className="hk-wl-col-ask">{ask}</span>
                      <span className="hk-wl-col-spread">{spreadVal} pts</span>
                      <button
                        type="button"
                        className="hk-wl-remove-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onRemoveFromWatchlist) onRemoveFromWatchlist(sym);
                        }}
                        title="Remover da Watchlist"
                      >
                        ×
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* MODE 2: HDF EVIDENCE CARD */}
        {mode === 'evidence' && (
          <div className="hk-evidence-container">
            {!evidenceData ? (
              <div className="hk-empty-state">
                <span className="hk-empty-icon">🛡️</span>
                <p>Nenhuma evidência HDF selecionada no gráfico.</p>
                <span className="hk-empty-subtext">Selecione uma evidência no Centro HDF para inspecionar P1 e P2.</span>
              </div>
            ) : (
              <div className="hk-evidence-card">
                <div className={`hk-evidence-hero ${evidenceData.direction?.toLowerCase()}`}>
                  <div className="hk-evidence-hero-top">
                    <span className="hk-evidence-badge">HDF EVIDÊNCIA QUANTITATIVA</span>
                    <span className="hk-evidence-state">{evidenceData.variant_stage || evidenceData.current_state || 'HDF_D'}</span>
                  </div>
                  <h3 className="hk-evidence-symbol">{evidenceData.symbol || selectedSymbol} • {evidenceData.timeframe || 'H1'}</h3>
                  <span className="hk-evidence-dir-text">
                    {evidenceData.direction === 'BULLISH' ? '🔺 EVIDÊNCIA ALTISTA (BULLISH)' : '🔻 EVIDÊNCIA BAIXISTA (BEARISH)'}
                  </span>
                </div>

                <div className="hk-evidence-section">
                  <h4 className="hk-section-title">GEOMETRIA DOS PIVÔS (P1 → P2)</h4>
                  <div className="hk-grid-2">
                    <div className="hk-stat-box">
                      <span className="hk-stat-label">P1 Tempo</span>
                      <span className="hk-stat-val">{evidenceData.pivot_1_time || '--'}</span>
                    </div>
                    <div className="hk-stat-box">
                      <span className="hk-stat-label">P1 RSI</span>
                      <span className="hk-stat-val accent">{evidenceData.pivot_1_rsi ? Number(evidenceData.pivot_1_rsi).toFixed(1) : '--'}</span>
                    </div>
                    <div className="hk-stat-box">
                      <span className="hk-stat-label">P2 Tempo</span>
                      <span className="hk-stat-val">{evidenceData.pivot_2_time || '--'}</span>
                    </div>
                    <div className="hk-stat-box">
                      <span className="hk-stat-label">P2 RSI</span>
                      <span className="hk-stat-val accent">{evidenceData.pivot_2_rsi ? Number(evidenceData.pivot_2_rsi).toFixed(1) : '--'}</span>
                    </div>
                  </div>
                </div>

                <div className="hk-evidence-section">
                  <h4 className="hk-section-title">FUNIL DE CONFLUÊNCIA HDF</h4>
                  <div className="hk-checklist">
                    <div className={`hk-check-item ${evidenceData.divergence_confirmed ?? true ? 'active' : ''}`}>
                      {evidenceData.divergence_confirmed ?? true ? '✓' : '✕'} Divergência Matemática Regular (HDF_D)
                    </div>
                    <div className={`hk-check-item ${evidenceData.volume_pass ? 'active' : ''}`}>
                      {evidenceData.volume_pass ? '✓' : '✕'} Volume Relativo (MA20 ≥ 1.0x): {evidenceData.relative_volume ? Number(evidenceData.relative_volume).toFixed(2) : '--'}x
                    </div>
                    <div className={`hk-check-item ${evidenceData.pattern_pass ? 'active' : ''}`}>
                      {evidenceData.pattern_pass ? '✓' : '✕'} Padrão de Reversão (SAME_BAR): {evidenceData.pattern_type || 'Nenhum'}
                    </div>
                    <div className={`hk-check-item ${evidenceData.candidate_created ? 'active' : ''}`}>
                      {evidenceData.candidate_created ? '✓' : '✕'} Candidato HDF_DVP Criado
                    </div>
                    <div className={`hk-check-item ${evidenceData.armed ? 'active' : ''}`}>
                      {evidenceData.armed ? '✓' : '✕'} Setup Armado (ARMED)
                    </div>
                    <div className={`hk-check-item ${evidenceData.activated ? 'active' : ''}`}>
                      {evidenceData.activated ? '✓' : '✕'} Setup Ativado (ACTIVATED)
                    </div>
                  </div>
                </div>

                <div className="hk-evidence-section">
                  <h4 className="hk-section-title">AVISO DE OBSERVABILIDADE</h4>
                  <p className="hk-evidence-explanation" style={{ fontSize: '10px', color: 'var(--hk-text-muted)' }}>
                    Evidência observacional HDF gerada deterministicamente pelo backend. Não constitui recomendação de investimento ou sinal de execução real.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}



        {/* MODE 4: SYSTEM DIAGNOSTICS */}
        {mode === 'system' && (
          <div className="hk-system-view">
            <h4 className="hk-section-title">DIAGNÓSTICO E INFRAESTRUTURA</h4>
            <div className="hk-system-card">
              <div className="hk-sys-item">
                <span className="hk-sys-label">MetaTrader 5 Adapter</span>
                <span className={`hk-sys-status ${systemStatus === 'ONLINE' ? 'green' : 'red'}`}>
                  {systemStatus === 'ONLINE' ? `CONECTADO${systemHealth?.broker_name ? ` (${systemHealth.broker_name})` : ''}` : 'DESCONECTADO'}
                </span>
              </div>
              <div className="hk-sys-item">
                <span className="hk-sys-label">Universo Sombra</span>
                <span className="hk-sys-status cyan">{operationalCount}/{totalCount} Combinadores Ativos</span>
              </div>
              <div className="hk-sys-item">
                <span className="hk-sys-label">Execução Corretora</span>
                <span className="hk-sys-status amber">🔒 TRAVADA (SAFETY LOCK)</span>
              </div>
              <div className="hk-sys-item">
                <span className="hk-sys-label">FastAPI Engine</span>
                <span className="hk-sys-status green">{systemHealth ? `RESPONDENDO${Number.isFinite(systemHealth.latency_ms) ? ` • ${systemHealth.latency_ms.toFixed(2)} ms leitura de símbolos` : ''}` : 'INDISPONÍVEL'}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
