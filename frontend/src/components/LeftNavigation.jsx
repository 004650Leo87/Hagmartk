import React from 'react';

export default function LeftNavigation({
  activeTab,
  onSelectTab,
  isExpanded,
  onToggleExpand,
}) {
  const NAV_ITEMS = [
    { id: 'chart', label: 'Gráfico / Cockpit', icon: '📊' },
    { id: 'watchlist', label: 'Mercado / Ativos', icon: '⌁' },
    { id: 'shadow', label: 'Shadow Monitor (39)', icon: '🛡️' },
    { id: 'strategies', label: 'Estratégia HDF', icon: '◇' },
    { id: 'backtest', label: 'Backtest Lab', icon: '↻' },
    { id: 'ai', label: 'IA Hagmartk', icon: '🤖' },
    { id: 'automation', label: 'Automação / Safety', icon: '⚡' },
    { id: 'alerts', label: 'Centro de Alertas', icon: '🔔' },
    { id: 'settings', label: 'Configurações', icon: '⚙' },
  ];

  return (
    <aside className={`hk-left-nav ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div className="hk-nav-top">
        <button
          type="button"
          className="hk-nav-toggle-btn"
          onClick={onToggleExpand}
          title={isExpanded ? 'Recolher Menu' : 'Expandir Menu'}
        >
          <span>{isExpanded ? '◀' : '▶'}</span>
        </button>
      </div>

      <nav className="hk-nav-list">
        {NAV_ITEMS.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`hk-nav-item ${isActive ? 'active' : ''}`}
              onClick={() => onSelectTab(item.id)}
              title={!isExpanded ? item.label : undefined}
            >
              <span className="hk-nav-icon">{item.icon}</span>
              {isExpanded && <span className="hk-nav-label">{item.label}</span>}
              {isActive && <div className="hk-nav-active-indicator" />}
            </button>
          );
        })}
      </nav>

      <div className="hk-nav-bottom">
        <div className="hk-safety-badge" title="Broker Execution DISABLED">
          <span className="hk-safety-icon">🔒</span>
          {isExpanded && <span className="hk-safety-text">TRADING OFF</span>}
        </div>
      </div>
    </aside>
  );
}
