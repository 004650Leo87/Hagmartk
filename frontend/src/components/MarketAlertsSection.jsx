import React, { useEffect, useMemo, useState } from 'react';
import { getRecentMarketAlerts } from '../services/api';

const FILTERS = ['TODOS', 'DVP', 'TC', 'ORB'];

function Level({ label, value, tone = 'normal' }) {
  if (!value) return null;
  return (
    <div className="bg-slate-950/70 border border-slate-800 rounded-lg px-3 py-2">
      <span className="text-[10px] text-slate-500 block">{label}</span>
      <strong className={`font-mono text-xs ${tone === 'stop' ? 'text-red-300' : tone === 'target' ? 'text-emerald-300' : 'text-slate-100'}`}>
        {value}
      </strong>
    </div>
  );
}

export default function MarketAlertsSection({ onSelectAlert }) {
  const [alerts, setAlerts] = useState([]);
  const [filter, setFilter] = useState('TODOS');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const data = await getRecentMarketAlerts(60, 'ALL');
        if (mounted) setAlerts(data?.alerts || []);
      } catch (err) {
        console.error('Falha ao carregar alertas HAGMARTK:', err);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    const timer = setInterval(load, 5000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);
  const filtered = useMemo(() => {
    if (filter === 'TODOS') return alerts;
    return alerts.filter((item) => item.strategy_key === filter);
  }, [alerts, filter]);

  return (
    <div className="strategy-dashboard">
      <div className="strategy-hero-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800 }}>🔔 Ocorrências HAGMARTK</h2>
            <p style={{ margin: '5px 0 0', color: '#94a3b8', fontSize: '12px' }}>
              Mesmo padrão visual do Telegram, com horário de Brasília e níveis operacionais.
            </p>
          </div>
          <div className="hk-pills-bar" style={{ display: 'flex', gap: '6px' }}>
            {FILTERS.map((item) => (
              <button key={item} type="button" className={`hk-pill-btn ${filter === item ? 'active' : ''}`} onClick={() => setFilter(item)}>
                {item === 'TC' ? 'TEORIA DOS CICLOS' : item}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && alerts.length === 0 ? (
        <div className="hk-card full-width"><div className="hk-card-body">Carregando ocorrências...</div></div>
      ) : filtered.length === 0 ? (
        <div className="hk-card full-width"><div className="hk-card-body">Nenhuma ocorrência registrada para este filtro.</div></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((alert, index) => (
            <div key={`${alert.strategy_key}-${alert.event_time_utc || index}-${alert.symbol}`} className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <div className="text-sm font-extrabold text-slate-100">{alert.event_icon} {alert.strategy}</div>
                  <div className="text-[11px] font-bold text-emerald-300 mt-1">{alert.event_label}</div>
                </div>
                <span className="text-[10px] px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-400">SHADOW</span>
              </div>
              <div className="space-y-1.5 text-xs text-slate-300">
                <div>📌 <strong>{alert.symbol}</strong> {alert.timeframe && alert.timeframe !== '—' ? `• ${alert.timeframe}` : ''}</div>
                <div>🕒 {alert.time_brazil}</div>
                <div>{alert.direction_icon} {alert.direction}</div>
              </div>

              {(alert.entry || alert.stop || (alert.targets || []).length > 0) && (
                <div className="grid grid-cols-2 gap-2 mt-3">
                  <Level label="Entrada" value={alert.entry} />
                  <Level label="Stop" value={alert.stop} tone="stop" />
                  {(alert.targets || []).map((target) => (
                    <Level key={target.label} label={target.label} value={target.value} tone="target" />
                  ))}
                </div>
              )}

              {alert.result && (
                <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/70 px-3 py-2 text-xs">
                  📊 Resultado: <strong className="text-slate-100">{alert.result}</strong>
                </div>
              )}
              {alert.note && <div className="mt-2 text-[11px] text-slate-400">ℹ️ {alert.note}</div>}

              {onSelectAlert && alert.symbol && (
                <button
                  type="button"
                  className="indicator-preset-btn"
                  style={{ width: '100%', marginTop: '12px', fontSize: '11px' }}
                  onClick={() => onSelectAlert(alert)}
                >
                  ABRIR ATIVO NO GRÁFICO
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
