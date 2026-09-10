import React, { useEffect, useMemo, useState } from 'react';
import EvidenceChart from './EvidenceChart';
import { getRecentMarketAlerts, getStrategyPerformance } from '../services/api';
import './EvidenceDashboard.css';

const FILTERS = [
  { key: 'ALL', label: 'Todos' },
  { key: 'DVP', label: 'DVP' },
  { key: 'TC', label: 'TDC' },
  { key: 'ORB', label: 'ORB' },
];

function HMLogo({ small = false }) {
  return <img className={`ev-hm-logo ${small ? 'small' : ''}`} src="/hm-logo.png" alt="HAGMARTK HM" />;
}
function strategyLabel(key) {
  if (key === 'TC') return 'HAGMARTK TDC';
  if (key === 'DVP') return 'HAGMARTK DVP';
  if (key === 'ORB') return 'HAGMARTK ORB';
  return 'HAGMARTK';
}

function statusInfo(alert) {
  const kind = String(alert?.event_kind || '').toUpperCase();
  if (kind === 'STOP') return { text: 'STOP', tone: 'danger' };
  if (kind === 'TARGET') return { text: alert?.event_label || 'ALVO', tone: 'success' };
  if (kind === 'PARTIAL') return { text: 'PARCIAL', tone: 'success' };
  if (kind === 'CLOSED') return { text: 'ENCERRADA', tone: 'neutral' };
  if (kind === 'EXPIRED') return { text: 'ENCERRADA', tone: 'neutral' };
  if (kind === 'ENTRY') return { text: 'EM ANDAMENTO', tone: 'active' };
  if (kind === 'SIGNAL' || kind === 'WATCH') return { text: 'OBSERVAÇÃO', tone: 'active' };
  return { text: 'REGISTRADA', tone: 'neutral' };
}

function calcRR(alert) {
  const entry = Number(alert?.entry);
  const stop = Number(alert?.stop);
  const targets = (alert?.targets || []).map((item) => Number(item?.value)).filter(Number.isFinite);
  if (!Number.isFinite(entry) || !Number.isFinite(stop) || !targets.length) return '—';
  const risk = Math.abs(entry - stop);
  if (!risk) return '—';
  const reward = Math.max(...targets.map((target) => Math.abs(target - entry)));
  return `1:${(reward / risk).toFixed(1).replace('.', ',')}`;
}

function shortTime(value) {
  const match = String(value || '').match(/•\s*(\d{2}:\d{2})/);
  return match ? match[1] : '—';
}
export default function EvidenceDashboard({ onOpenStrategies, onOpenLegacyChart, onOpenReports }) {
  const [alerts, setAlerts] = useState([]);
  const [filter, setFilter] = useState('ALL');
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [performance, setPerformance] = useState(null);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function loadAlerts() {
      try {
        const response = await getRecentMarketAlerts(100, 'ALL');
        if (!mounted) return;
        const rows = response?.alerts || [];
        setAlerts(rows);
        setOnline(true);
        setSelectedId((current) => {
          if (current && rows.some((row) => (row.operation_id || row.event_time_utc) === current)) return current;
          return rows[0] ? (rows[0].operation_id || rows[0].event_time_utc || '') : '';
        });
      } catch (err) {
        console.error('Falha ao carregar Centro de Ocorrências:', err);
        if (mounted) setOnline(false);
      }
    }
    loadAlerts();
    const timer = setInterval(loadAlerts, 5000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  useEffect(() => {
    let mounted = true;
    getStrategyPerformance().then((data) => {
      if (mounted) setPerformance(data?.strategies || null);
    }).catch((err) => console.error('Falha ao carregar desempenho:', err));
    return () => { mounted = false; };
  }, []);
  const operations = useMemo(() => {
    const map = new Map();
    alerts.forEach((row) => {
      const key = row.operation_id || `${row.strategy_key}:${row.symbol}:${row.event_time_utc}`;
      if (!map.has(key)) map.set(key, row);
    });
    return Array.from(map.values());
  }, [alerts]);

  const counts = useMemo(() => ({
    ALL: operations.length,
    DVP: operations.filter((row) => row.strategy_key === 'DVP').length,
    TC: operations.filter((row) => row.strategy_key === 'TC').length,
    ORB: operations.filter((row) => row.strategy_key === 'ORB').length,
  }), [operations]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return operations.filter((row) => {
      if (filter !== 'ALL' && row.strategy_key !== filter) return false;
      if (!needle) return true;
      return `${row.symbol} ${row.strategy} ${row.direction}`.toLowerCase().includes(needle);
    });
  }, [operations, filter, query]);

  const selected = useMemo(() => {
    const exact = alerts.find((row) => (row.operation_id || row.event_time_utc) === selectedId);
    return exact || filtered[0] || alerts[0] || null;
  }, [alerts, filtered, selectedId]);

  const selectedStatus = statusInfo(selected);
  const perfRow = selected ? performance?.[selected.strategy_key] : null;

  return (
    <div className="ev-app">
      <header className="ev-header">
        <div className="ev-brand">
          <HMLogo />
          <div><div className="ev-brand-name">HAGMARTK</div><div className="ev-brand-sub">MARKET MONITORING</div><div className="ev-brand-tag">DISCIPLINA GERA EVIDÊNCIAS</div></div>
        </div>
        <nav className="ev-topnav">
          <button className="active" type="button">▥ <span>Painel de Evidências</span></button>
          <button type="button" onClick={onOpenStrategies}>◎ <span>Estratégias</span></button>
          <button type="button" onClick={onOpenReports}>▤ <span>Relatórios</span></button>
          <button type="button" onClick={onOpenLegacyChart}>↗ <span>Gráfico Completo</span></button>
        </nav>
        <div className="ev-header-motto">MERCADO<br />ESTRUTURA<br />DISCIPLINA<br />RESULTADOS</div>
      </header>
      <main className="ev-grid">
        <aside className="ev-occurrences ev-panel">
          <div className="ev-panel-title-row">
            <div><h2>Centro de Ocorrências</h2><p>Últimas sinalizações das estratégias HAGMARTK</p></div>
            <span className={`ev-live ${online ? '' : 'offline'}`}>● {online ? 'AO VIVO' : 'DEGRADADO'}</span>
          </div>
          <div className="ev-filter-row">
            {FILTERS.map((item) => (
              <button type="button" key={item.key} className={filter === item.key ? 'active' : ''}
                onClick={() => setFilter(item.key)}>{item.label}<b>{counts[item.key] || 0}</b></button>
            ))}
          </div>
          <div className="ev-search-row">
            <span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar ativo, estratégia..." />
          </div>
          <div className="ev-feed">
            {filtered.slice(0, 18).map((row) => {
              const id = row.operation_id || row.event_time_utc;
              const status = statusInfo(row);
              const active = selected && (selected.operation_id || selected.event_time_utc) === id;
              const buy = row.direction === 'COMPRA';
              return (
                <button type="button" key={`${id}-${row.event_code}`} className={`ev-feed-row ${active ? 'selected' : ''}`}
                  onClick={() => setSelectedId(id)}>
                  <div className="ev-feed-time">{shortTime(row.time_brazil)}</div>
                  <div className="ev-feed-main"><strong>{strategyLabel(row.strategy_key)}</strong><span>{row.symbol} · {row.timeframe}</span></div>
                  <div className={`ev-direction ${buy ? 'buy' : 'sell'}`}>{buy ? '↑ LONG' : '↓ SHORT'}</div>
                  <div className={`ev-chip ${status.tone}`}>{status.text}</div>
                </button>
              );
            })}
            {!filtered.length && <div className="ev-empty-feed">Nenhuma ocorrência neste filtro.</div>}
          </div>
          <blockquote>“Não é sobre prever o mercado.<br />É sobre reconhecer o que ele mostra.”<small>HAGMARTK</small></blockquote>
        </aside>
        <section className="ev-center">
          <div className="ev-chart-panel ev-panel">
            <div className="ev-chart-head">
              <div className="ev-chart-title"><span className="ev-gold-bars">▥</span><div><h2>{selected ? strategyLabel(selected.strategy_key) : 'HAGMARTK'}</h2><p>Evidência no Gráfico · {selected?.timeframe || '—'}</p></div></div>
              <div className="ev-chart-controls">
                <span>{selected?.symbol || '—'}</span><span>{selected?.timeframe || '—'}</span><span>{selected?.time_brazil?.split(' • ')[0] || '—'}</span>
              </div>
            </div>
            <EvidenceChart alert={selected} />
          </div>

          <div className="ev-dvp-panel ev-panel">
            <div className="ev-subtitle"><span className="ev-gold-bars">▥</span><div><h3>HAGMARTK DVP</h3><p>Identificação do Candle Gatilho</p></div></div>
            <div className="ev-dvp-grid">
              <div className="ev-trigger-card"><strong>Candle Gatilho de COMPRA (LONG)</strong><div className="ev-mini-candles buy"><i></i><i></i><i className="trigger"></i><i></i><i></i><i></i></div><p>No DVP, o candle gatilho de compra é pintado de <b>BRANCO</b>, sinalizando o ponto de entrada.</p></div>
              <div className="ev-trigger-card"><strong>Candle Gatilho de VENDA (SHORT)</strong><div className="ev-mini-candles sell"><i></i><i></i><i></i><i className="trigger"></i><i></i><i></i></div><p>No DVP, o candle gatilho de venda é pintado de <b>AMARELO</b>, sinalizando o ponto de entrada.</p></div>
            </div>
          </div>
        </section>
        <aside className="ev-details ev-panel">
          <h2>Detalhes da Ocorrência</h2>
          {selected ? (
            <>
              <div className="ev-detail-hero"><span className={selected.direction === 'COMPRA' ? 'buy-dot' : 'sell-dot'}></span><div><strong>{strategyLabel(selected.strategy_key)}</strong><small>{selected.event_label}</small></div></div>
              <div className="ev-detail-list">
                <div><span>Estratégia</span><b>{selected.strategy_key === 'TC' ? 'TDC' : selected.strategy_key}</b></div>
                <div><span>Ativo</span><b>{selected.symbol}</b></div>
                <div><span>Horário (Brasília)</span><b>{selected.time_brazil}</b></div>
                <div><span>Direção</span><b className={selected.direction === 'COMPRA' ? 'positive' : 'negative'}>{selected.direction === 'COMPRA' ? '↑ LONG' : '↓ SHORT'}</b></div>
                <div><span>Entrada</span><b>{selected.entry || '—'}</b></div>
                {(selected.targets || []).map((target) => <div key={target.label}><span>{target.label}</span><b>{target.value}</b></div>)}
                <div><span>Stop</span><b>{selected.stop || '—'}</b></div>
                <div><span>Status</span><b><em className={`ev-chip ${selectedStatus.tone}`}>{selectedStatus.text}</em></b></div>
                <div><span>Resultado</span><b>{selected.result || (perfRow?.completed_trades ? 'EM APURAÇÃO' : '—')}</b></div>
                <div><span>R/R Previsto</span><b>{calcRR(selected)}</b></div>
                <div><span>Acompanhamento</span><b>Shadow / Simulação</b></div>
              </div>
              <button className="ev-open-chart" type="button" onClick={onOpenLegacyChart}>Ver no Gráfico Completo ↗</button>
              <div className="ev-safety-note">🔒 Nenhuma ordem real foi enviada.</div>
            </>
          ) : <div className="ev-no-selection">Aguardando ocorrência.</div>}
          <div className="ev-quote-card">“Evidências transformam método em confiança.”<small>HAGMARTK</small></div>
        </aside>
      </main>
      <footer className="ev-footer">
        <span>HAGMARTK &nbsp;|&nbsp; MARKET MONITORING</span>
        <span>ESTRATÉGIA &nbsp;·&nbsp; PROCESSO &nbsp;·&nbsp; EVIDÊNCIAS &nbsp;·&nbsp; EVOLUÇÃO</span>
        <span className={online ? 'online' : 'offline'}>● {online ? 'SISTEMA ONLINE' : 'SISTEMA DEGRADADO'}</span>
      </footer>
    </div>
  );
}
