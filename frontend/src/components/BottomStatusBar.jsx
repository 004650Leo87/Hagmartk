import React, { useEffect, useState } from 'react';
import HdfActivityMeter from './HdfActivityMeter';

export default function BottomStatusBar({
  mt5Connected,
  shadowStatus,
  operationalCount = 33,
  totalCount = 39,
  lastActivity,
  isDrawerOpen,
  onToggleDrawer,
  activeDrawerTab,
  onSelectDrawerTab,
}) {
  const [utcTime, setUtcTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toISOString().substring(11, 19) + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <footer className="hk-statusbar-v3">
      {/* Optional Collapsible Bottom Drawer Content */}
      {isDrawerOpen && (
        <div className="hk-bottom-drawer-panel">
          <div className="hk-bottom-drawer-header">
            <div className="hk-bottom-drawer-tabs">
              {['POSITIONS', 'ORDERS', 'HISTORY', 'LOGS'].map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`hk-bottom-tab-btn ${activeDrawerTab === tab ? 'active' : ''}`}
                  onClick={() => onSelectDrawerTab && onSelectDrawerTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="hk-close-btn"
              onClick={onToggleDrawer}
              title="Fechar Drawer Inferior"
            >
              ×
            </button>
          </div>

          <div className="hk-bottom-drawer-body">
            {activeDrawerTab === 'POSITIONS' && (
              <div className="hk-drawer-empty">
                <span>🔒 Broker Execution: DISABLED. Nenhuma posição aberta na corretora.</span>
              </div>
            )}
            {activeDrawerTab === 'ORDERS' && (
              <div className="hk-drawer-empty">
                <span>Nenhuma ordem pendente no momento.</span>
              </div>
            )}
            {activeDrawerTab === 'HISTORY' && (
              <div className="hk-drawer-empty">
                <span>Histórico de ordens limpo (Modo Observacional Shadow).</span>
              </div>
            )}
            {activeDrawerTab === 'LOGS' && (
              <div className="hk-drawer-logs">
                <div className="hk-log-line"><code>[SYSTEM] MetaTrader 5 Adapter: Connected (Tickmill Live)</code></div>
                <div className="hk-log-line"><code>[SHADOW] Scanner Loop Active: {operationalCount}/{totalCount} combinations operational</code></div>
                <div className="hk-log-line"><code>[HDF] Hero Divergence Framework V1 Engine Active</code></div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Compact Bottom Strip */}
      <div className="hk-statusbar-strip">
        <div className="hk-statusbar-left">
          <button
            type="button"
            className={`hk-bottom-drawer-toggle ${isDrawerOpen ? 'active' : ''}`}
            onClick={onToggleDrawer}
            title={isDrawerOpen ? 'Recolher Drawer' : 'Abrir Painel Inferior (Positions/Orders/Logs)'}
          >
            <span>{isDrawerOpen ? '▼ PAINEL INFERIOR' : '▲ PAINEL INFERIOR'}</span>
          </button>

          <div className="hk-statusbar-sep">│</div>

          <div className={`hk-status-item-compact ${mt5Connected ? 'success' : 'error'}`}>
            <span className="hk-status-dot-sm" />
            <span>MT5: {mt5Connected ? 'CONECTADO' : 'DESCONECTADO'}</span>
          </div>

          <div className="hk-statusbar-sep">│</div>

          <div className="hk-status-item-compact info">
            <span>SHADOW: {operationalCount}/{totalCount}</span>
          </div>

          <div className="hk-statusbar-sep">│</div>

          <HdfActivityMeter />

          <div className="hk-statusbar-sep">│</div>

          <div className="hk-status-item-compact warning">
            <span>🔒 EXECUTION OFF</span>
          </div>
        </div>

        <div className="hk-statusbar-right">
          {lastActivity && (
            <>
              <span className="hk-status-subtext">Varredura: {lastActivity}</span>
              <div className="hk-statusbar-sep">│</div>
            </>
          )}
          <span className="hk-status-time">{utcTime}</span>
        </div>
      </div>
    </footer>
  );
}
