import React, { useEffect, useMemo, useState } from 'react';
import { getRecentMarketAlerts } from '../services/api';

export default function AlertCenterDrawer({ isOpen, onClose, onSelectEvent }) {
  const [alerts, setAlerts] = useState([]);
  const [filter, setFilter] = useState('TODOS');

  useEffect(() => {
    if (!isOpen) return undefined;
    let mounted = true;
    async function load() {
      try {
        const data = await getRecentMarketAlerts(40, 'ALL');
        if (mounted) setAlerts(data?.alerts || []);
      } catch (err) {
        console.error('Falha no Centro de Ocorrências:', err);
      }
    }
    load();
    const timer = setInterval(load, 5000);
    return () => { mounted = false; clearInterval(timer); };
  }, [isOpen]);

  const filtered = useMemo(() => {
    if (filter === 'TODOS') return alerts;
    return alerts.filter((item) => item.strategy_key === filter);
  }, [alerts, filter]);

  if (!isOpen) return null;
  return (
    <div className="hk-alert-side-drawer" role="complementary" aria-label="Centro de Ocorrências HAGMARTK">
      <div className="hk-drawer-header">
        <div className="hk-drawer-title-group">
          <h3>🔔 OCORRÊNCIAS HAGMARTK</h3>
          <span className="hk-subtext">{alerts.length} registros recentes • horário de Brasília</span>
        </div>
        <button type="button" className="hk-close-btn" onClick={onClose} title="Fechar">×</button>
      </div>

      <div className="hk-pills-bar" style={{ display: 'flex', gap: '6px', padding: '8px 12px', overflowX: 'auto' }}>
        {['TODOS', 'DVP', 'TC', 'ORB'].map((item) => (
          <button
            key={item}
            type="button"
            className={`hk-pill-btn ${filter === item ? 'active' : ''}`}
            style={{ padding: '5px 10px', fontSize: '10px', fontWeight: 700, whiteSpace: 'nowrap' }}
            onClick={() => setFilter(item)}
          >
            {item === 'TC' ? 'TEORIA DOS CICLOS' : item}
          </button>
        ))}
      </div>

      <div className="hk-drawer-body">
        {filtered.length === 0 ? (
          <div className="hk-empty">Nenhuma ocorrência registrada para este filtro.</div>
        ) : filtered.map((alert, index) => (
          <div
            key={`${alert.strategy_key}-${alert.event_time_utc || index}-${alert.symbol}`}
            className={`hk-alert-card ${alert.direction === 'COMPRA' ? 'bullish' : alert.direction === 'VENDA' ? 'bearish' : ''}`}
            style={{ cursor: 'pointer', padding: '11px 12px', marginBottom: '8px' }}
            onClick={() => onSelectEvent && onSelectEvent(alert)}
          >
            <div className="hk-alert-top">
              <span className="hk-alert-symbol">{alert.event_icon} {alert.strategy}</span>
              <span className={`hk-alert-dir ${alert.direction === 'COMPRA' ? 'buy' : 'sell'}`}>{alert.direction_icon} {alert.direction}</span>
            </div>
            <div className="hk-alert-mid" style={{ display: 'block', margin: '7px 0' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--hk-accent-cyan)' }}>{alert.event_label}</div>
              <div style={{ fontSize: '11px', marginTop: '4px' }}>📌 {alert.symbol} {alert.timeframe && alert.timeframe !== '—' ? `• ${alert.timeframe}` : ''}</div>
              <div style={{ fontSize: '10px', color: 'var(--hk-text-muted)', marginTop: '3px' }}>🕒 {alert.time_brazil}</div>
            </div>
            {(alert.entry || alert.stop || (alert.targets || []).length > 0) && (
              <div style={{ fontSize: '10px', color: 'var(--hk-text-muted)', lineHeight: 1.6 }}>
                {alert.entry && <div>Entrada: <strong style={{ color: 'var(--hk-text)' }}>{alert.entry}</strong></div>}
                {alert.stop && <div>Stop: <strong style={{ color: '#f87171' }}>{alert.stop}</strong></div>}
                {(alert.targets || []).map((target) => (
                  <div key={target.label}>{target.label}: <strong style={{ color: '#34d399' }}>{target.value}</strong></div>
                ))}
              </div>
            )}
            {alert.result && <div style={{ marginTop: '6px', fontSize: '11px' }}>📊 <strong>{alert.result}</strong></div>}
            <div className="hk-alert-bottom" style={{ marginTop: '7px' }}>
              <span className="hk-alert-action">Abrir ativo no gráfico →</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
