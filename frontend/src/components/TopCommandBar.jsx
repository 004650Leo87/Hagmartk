import React, { useState, useRef, useEffect } from 'react';

export default function TopCommandBar({
  selectedSymbol,
  onSelectSymbolClick,
  timeframe,
  onSelectTimeframe,
  onToggleEvidenceCard,
  hasEvidence,
  showRSI = true,
  onToggleRSI,
  onToggleAlerts,
  alertCount,
  systemStatus,
  systemHealth,
  theme,
  onToggleTheme,
  isZenMode,
  onToggleZen,
  operationalCount = 39,
  totalCount = 39,
}) {
  const FAVORITES = ['M5', 'M15', 'H1', 'H4'];
  const ALL_TIMEFRAMES = [
    { group: 'Minutos', items: ['M1', 'M5', 'M15', 'M30'] },
    { group: 'Horas', items: ['H1', 'H4'] },
    { group: 'Dias', items: ['D1'] },
  ];

  const [showTfDropdown, setShowTfDropdown] = useState(false);
  const [showSystemPopover, setShowSystemPopover] = useState(false);

  const tfDropdownRef = useRef(null);
  const systemPopoverRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (tfDropdownRef.current && !tfDropdownRef.current.contains(e.target)) {
        setShowTfDropdown(false);
      }
      if (systemPopoverRef.current && !systemPopoverRef.current.contains(e.target)) {
        setShowSystemPopover(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const isOnline = systemStatus === 'ONLINE';

  return (
    <header className="hk-topbar">
      <div className="hk-topbar-left">
        <div className="hk-logo">
          <span className="hk-logo-icon">❖</span>
          <span className="hk-logo-text">HAGMARTK</span>
        </div>

        <div className="hk-topbar-divider" />

        {/* Symbol Selector */}
        <button
          type="button"
          className="hk-symbol-btn"
          onClick={onSelectSymbolClick}
          title="Selecionar Ativo (Ctrl+K)"
        >
          <span className="hk-symbol-name">{selectedSymbol || 'XAUUSD'}</span>
          <span className="hk-symbol-search-icon">🔍</span>
        </button>

        {/* Timeframe Selector V3 (Favorites + Dropdown) */}
        <div className="hk-tf-container" ref={tfDropdownRef}>
          <div className="hk-tf-group">
            {FAVORITES.map((tf) => (
              <button
                key={tf}
                type="button"
                className={`hk-tf-btn ${timeframe === tf ? 'active' : ''}`}
                onClick={() => {
                  onSelectTimeframe(tf);
                  setShowTfDropdown(false);
                }}
              >
                {tf}
              </button>
            ))}

            <button
              type="button"
              className={`hk-tf-dropdown-trigger ${!FAVORITES.includes(timeframe) ? 'active' : ''}`}
              onClick={() => setShowTfDropdown((prev) => !prev)}
              title="Mais períodos"
            >
              {!FAVORITES.includes(timeframe) ? timeframe : '▼'}
            </button>
          </div>

          {showTfDropdown && (
            <div className="hk-tf-menu">
              {ALL_TIMEFRAMES.map((sec) => (
                <div key={sec.group} className="hk-tf-section">
                  <span className="hk-tf-section-title">{sec.group}</span>
                  <div className="hk-tf-section-grid">
                    {sec.items.map((tf) => (
                      <button
                        key={tf}
                        type="button"
                        className={`hk-tf-menu-item ${timeframe === tf ? 'selected' : ''}`}
                        onClick={() => {
                          onSelectTimeframe(tf);
                          setShowTfDropdown(false);
                        }}
                      >
                        {tf}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="hk-topbar-center" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        {/* Evidence Card Trigger */}
        <button
          type="button"
          className={`hk-topbar-action-btn ${hasEvidence ? 'has-evidence' : ''}`}
          onClick={onToggleEvidenceCard}
          title="Ver Parecer de Evidência HDF"
        >
          <span className="hk-btn-icon">⚡</span>
          <span className="hk-btn-label">Evidência HDF</span>
          {hasEvidence && <span className="hk-pulse-dot" />}
        </button>

        {/* RSI Pane Toggle Button */}
        <button
          type="button"
          className={`hk-topbar-action-btn ${showRSI ? 'active' : ''}`}
          onClick={onToggleRSI}
          title={showRSI ? "Ocultar Pane RSI (14)" : "Exibir Pane RSI (14)"}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}
        >
          <span className="hk-btn-icon">📈</span>
          <span className="hk-btn-label">RSI 14</span>
          <span>{showRSI ? '👁' : '🙈'}</span>
        </button>
      </div>

      <div className="hk-topbar-right">
        {/* Zen / Focus Mode Toggle */}
        <button
          type="button"
          className={`hk-topbar-action-btn ${isZenMode ? 'active' : ''}`}
          onClick={onToggleZen}
          title={isZenMode ? 'Sair do Modo Zen' : 'Ativar Modo Zen (Foco Total)'}
        >
          <span className="hk-btn-label">{isZenMode ? '🔲 Sair do Zen' : '🧘 Modo Zen'}</span>
        </button>

        {/* Theme Switcher Button */}
        <button
          type="button"
          className="hk-topbar-action-btn"
          onClick={onToggleTheme}
          title="Alternar Tema (Black Piano / Light)"
        >
          <span className="hk-btn-label">{theme === 'black-piano' ? '🌙 Black Piano' : '☀️ Light'}</span>
        </button>

        {/* Alert Drawer Button */}
        <button
          type="button"
          className="hk-icon-btn"
          onClick={onToggleAlerts}
          title="Centro de Alertas"
        >
          <span>🔔</span>
          {alertCount > 0 && <span className="hk-badge-count">{alertCount}</span>}
        </button>

        {/* Minimal MT5 Status Chip & System Diagnostics Popover */}
        <div className="hk-system-popover-wrapper" ref={systemPopoverRef}>
          <button
            type="button"
            className={`hk-mt5-chip ${isOnline ? 'online' : 'degraded'}`}
            onClick={() => setShowSystemPopover((prev) => !prev)}
            title="Diagnóstico do Sistema & MT5"
          >
            <span className="hk-status-dot" />
            <span className="hk-status-text">MT5 ●</span>
          </button>

          {showSystemPopover && (
            <div className="hk-system-popover">
              <div className="hk-popover-header">
                <strong>DIAGNÓSTICO DO SISTEMA</strong>
                <span className={`hk-popover-badge ${isOnline ? 'online' : 'degraded'}`}>
                  {isOnline ? 'ONLINE' : 'DEGRADED'}
                </span>
              </div>
              <div className="hk-popover-body">
                <div className="hk-popover-row">
                  <span className="hk-popover-label">MetaTrader 5:</span>
                  <span className="hk-popover-val green">{isOnline ? `Conectado${systemHealth?.broker_name ? ` (${systemHealth.broker_name})` : ''}` : 'Desconectado'}</span>
                </div>
                <div className="hk-popover-row">
                  <span className="hk-popover-label">Universo Sombra:</span>
                  <span className="hk-popover-val cyan">{operationalCount}/{totalCount} Operacional</span>
                </div>
                <div className="hk-popover-row">
                  <span className="hk-popover-label">Execução Corretora:</span>
                  <span className="hk-popover-val amber">🔒 DESATIVADA (SAFETY LOCK)</span>
                </div>
                <div className="hk-popover-row">
                  <span className="hk-popover-label">Backend API:</span>
                  <span className="hk-popover-val green">{systemHealth ? `RESPONDENDO${Number.isFinite(systemHealth.latency_ms) ? ` • ${systemHealth.latency_ms.toFixed(2)} ms leitura de símbolos` : ''}` : 'INDISPONÍVEL'}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
