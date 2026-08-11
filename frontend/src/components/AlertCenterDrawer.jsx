import React, { useState, useEffect } from 'react';
import { getHDFEvidences } from '../services/api';

export default function AlertCenterDrawer({
  isOpen,
  onClose,
  events = [],
  onSelectEvent,
  selectedEventId,
  currentSymbol,
  currentTimeframe,
}) {
  const [activeTab, setActiveTab] = useState('EVIDENCIAS'); // 'EVIDENCIAS' | 'EVENTOS'
  const [evidences, setEvidences] = useState([]);
  const [evidenceFilter, setEvidenceFilter] = useState('TODOS');
  const [eventFilter, setEventFilter] = useState('TODOS');
  const [loadingEvidences, setLoadingEvidences] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    async function loadLiveEvidences() {
      try {
        setLoadingEvidences(true);
        const res = await getHDFEvidences(currentSymbol || 'XAUUSD', currentTimeframe || 'H1');
        setEvidences(res?.evidences || []);
      } catch (err) {
        console.error('Erro ao carregar HDFEvidences:', err);
      } finally {
        setLoadingEvidences(false);
      }
    }

    loadLiveEvidences();
  }, [isOpen, currentSymbol, currentTimeframe]);

  if (!isOpen) return null;

  // Filtragem de Evidências Live (exclui testes)
  const liveEvidences = evidences.filter((ev) => !ev.is_test);
  const filteredEvidences = liveEvidences.filter((ev) => {
    if (evidenceFilter === 'TODOS') return true;
    if (evidenceFilter === 'BULLISH') return ev.direction === 'BULLISH';
    if (evidenceFilter === 'BEARISH') return ev.direction === 'BEARISH';
    return true;
  });

  // Filtragem de Eventos Operacionais Live (exclui demos)
  const liveEvents = events.filter((evt) => !evt.event_id?.startsWith('test_') && !evt.is_test);
  const filteredEvents = liveEvents.filter((evt) => {
    if (eventFilter === 'TODOS') return true;
    if (eventFilter === 'ARMED') return evt.current_state === 'ARMED' || evt.status_code === 'ARMED';
    if (eventFilter === 'ACTIVATED') return evt.current_state === 'ACTIVATED' || evt.status_code === 'ACTIVATED';
    if (eventFilter === 'TERMINAL') return ['TARGET_HIT', 'STOP_HIT', 'TARGET_2R', 'STOPPED'].includes(evt.current_state || evt.status_code);
    return true;
  });

  return (
    <div className="hk-alert-side-drawer" role="complementary" aria-label="Centro HDF">
      <div className="hk-drawer-header">
        <div className="hk-drawer-title-group">
          <h3>⚡ CENTRO HDF</h3>
          <span className="hk-subtext">
            {activeTab === 'EVIDENCIAS'
              ? `${liveEvidences.length} evidências HDF live`
              : `${liveEvents.length} eventos operacionais live`}
          </span>
        </div>
        <button
          type="button"
          className="hk-close-btn"
          onClick={onClose}
          title="Recolher Gaveta"
        >
          ×
        </button>
      </div>

      {/* Primary Tabs */}
      <div className="hk-tab-strip" style={{ display: 'flex', borderBottom: '1px solid var(--hk-border)', padding: '6px 8px', gap: '6px' }}>
        <button
          type="button"
          className={`hk-pill-btn ${activeTab === 'EVIDENCIAS' ? 'active' : ''}`}
          style={{ flex: 1, padding: '6px 8px', fontSize: '11px', fontWeight: 700, whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}
          onClick={() => setActiveTab('EVIDENCIAS')}
        >
          <span>⚡ EVIDÊNCIAS HDF</span>
          <span style={{ opacity: 0.85 }}>({liveEvidences.length})</span>
        </button>
        <button
          type="button"
          className={`hk-pill-btn ${activeTab === 'EVENTOS' ? 'active' : ''}`}
          style={{ flex: 1, padding: '6px 8px', fontSize: '11px', fontWeight: 700, whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '4px' }}
          onClick={() => setActiveTab('EVENTOS')}
        >
          <span>🔔 EVENTOS</span>
          <span style={{ opacity: 0.85 }}>({liveEvents.length})</span>
        </button>
      </div>

      {/* Sub-Filters */}
      <div className="hk-pills-bar" style={{ display: 'flex', gap: '6px', padding: '8px 12px', overflowX: 'auto' }}>
        {(activeTab === 'EVIDENCIAS' ? ['TODOS', 'BULLISH', 'BEARISH'] : ['TODOS', 'ARMED', 'ACTIVATED', 'TERMINAL']).map((ft) => {
          const isSel = activeTab === 'EVIDENCIAS' ? evidenceFilter === ft : eventFilter === ft;
          const labelMap = {
            BULLISH: 'ALTISTA',
            BEARISH: 'BAIXISTA',
            ARMED: 'ARMADOS',
            ACTIVATED: 'ATIVADOS',
            TERMINAL: 'FINALIZADOS',
          };
          return (
            <button
              key={ft}
              type="button"
              className={`hk-pill-btn ${isSel ? 'active' : ''}`}
              style={{ padding: '4px 10px', fontSize: '10px', fontWeight: 600, whiteSpace: 'nowrap' }}
              onClick={() => (activeTab === 'EVIDENCIAS' ? setEvidenceFilter(ft) : setEventFilter(ft))}
            >
              {labelMap[ft] || ft}
            </button>
          );
        })}
      </div>

      {/* Content Body */}
      <div className="hk-drawer-body">
        {activeTab === 'EVIDENCIAS' ? (
          loadingEvidences ? (
            <div className="hk-empty">Carregando evidências HDF live...</div>
          ) : filteredEvidences.length === 0 ? (
            <div className="hk-empty">
              Nenhuma evidência HDF real registrada para {currentSymbol} ({currentTimeframe}).
            </div>
          ) : (
            filteredEvidences.map((ev, idx) => {
              const isBull = ev.direction === 'BULLISH';
              const evId = ev.evidence_id || `ev_${idx}`;
              const isSelected = selectedEventId === evId;

              return (
                <div
                  key={evId}
                  className={`hk-alert-card ${isBull ? 'bullish' : 'bearish'} ${isSelected ? 'selected' : ''}`}
                  style={{ cursor: 'pointer', padding: '10px 12px', marginBottom: '8px' }}
                  onClick={() => {
                    if (onSelectEvent) onSelectEvent(ev);
                  }}
                >
                  <div className="hk-alert-top">
                    <span className="hk-alert-symbol">{ev.symbol} • {ev.timeframe}</span>
                    <span className={`hk-alert-dir ${isBull ? 'buy' : 'sell'}`}>
                      {isBull ? 'EVIDÊNCIA ALTISTA' : 'EVIDÊNCIA BAIXISTA'}
                    </span>
                  </div>

                  <div className="hk-alert-mid" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '4px', margin: '6px 0' }}>
                    <div style={{ display: 'flex', gap: '8px', fontSize: '10px' }}>
                      <span className={ev.divergence_confirmed ? 'green' : 'gray'}>Divergência ✓</span>
                      <span className={ev.volume_pass ? 'green' : 'gray'}>Volume {ev.volume_pass ? '✓' : '✕'} ({ev.relative_volume?.toFixed(2) || '0.0'})</span>
                      <span className={ev.pattern_pass ? 'green' : 'gray'}>Padrão {ev.pattern_pass ? '✓' : '✕'}</span>
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--hk-text-muted)' }}>
                      P1: {ev.pivot_1_time} | P2: {ev.pivot_2_time}
                    </div>
                  </div>

                  <div className="hk-alert-bottom">
                    <span className="hk-alert-action" style={{ fontSize: '11px', color: 'var(--hk-accent-cyan)' }}>
                      {isSelected ? '✓ EM EXIBIÇÃO NO GRÁFICO' : 'Focar no Gráfico (Marcador HDF) →'}
                    </span>
                  </div>
                </div>
              );
            })
          )
        ) : filteredEvents.length === 0 ? (
          <div className="hk-empty">Nenhum evento operacional para o filtro selecionado.</div>
        ) : (
          filteredEvents.map((evt, idx) => {
            const isBull = evt.direction === 'BULLISH';
            const evtId = evt.event_id || evt.id || `evt_${idx}`;
            const isSelected = selectedEventId === evtId;

            return (
              <div
                key={evtId}
                className={`hk-alert-card ${isBull ? 'bullish' : 'bearish'} ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  if (onSelectEvent) onSelectEvent(evt);
                }}
              >
                <div className="hk-alert-top">
                  <span className="hk-alert-symbol">{evt.symbol} • {evt.timeframe}</span>
                  <span className={`hk-alert-dir ${isBull ? 'buy' : 'sell'}`}>
                    {isBull ? 'COMPRA' : 'VENDA'}
                  </span>
                </div>
                <div className="hk-alert-mid">
                  <span className="hk-alert-state">{evt.current_state || evt.status_code || 'ARMED'}</span>
                  <span className="hk-alert-time">{evt.event_time ? new Date(evt.event_time).toLocaleTimeString() : '--'}</span>
                </div>
                <div className="hk-alert-bottom">
                  <span className="hk-alert-action">{isSelected ? '✓ EM EXIBIÇÃO NO GRÁFICO' : 'Focar no Gráfico →'}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
