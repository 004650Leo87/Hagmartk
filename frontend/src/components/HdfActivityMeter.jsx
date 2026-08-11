import React, { useEffect, useRef, useState } from 'react';
import { getShadowHeartbeat, getShadowScanners } from '../services/api';

const TOTAL_LEDS = 12;
const PULSE_DURATION_MS = 700; // Visual persistence duration (700ms) for human perception

export default function HdfActivityMeter() {
  const [telemetry, setTelemetry] = useState(null);
  const [scanners, setScanners] = useState([]);
  const [statusText, setStatusText] = useState('LIVE');
  const [statusColor, setStatusColor] = useState('#21d68d');
  const [activeLeds, setActiveLeds] = useState(0);
  const [pulseColor, setPulseColor] = useState('#00f2fe');
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('RESUMO');
  const [lastPulseType, setLastPulseType] = useState('NONE');
  const [lastPulseTime, setLastPulseTime] = useState('--');
  const [isCandidateHovered, setIsCandidateHovered] = useState(false);

  const pulseTimerRef = useRef(null);

  // Multi-state delta tracking
  const prevRef = useRef({
    scanCycles: null,
    evaluations: null,
    hdfD: null,
    candidates: null,
    armed: null,
    activated: null,
  });

  useEffect(() => {
    let isMounted = true;

    async function pollTelemetry() {
      try {
        const data = await getShadowHeartbeat();
        if (!isMounted || !data) return;

        setTelemetry(data);

        const totals = data.totals || {};
        const currScan = totals.scan_cycles || 0;
        const currEval = totals.evaluations || 0;
        const currHdfD = totals.hdf_d || 0;
        const currCand = totals.candidates || 0;
        const currArmed = totals.armed || 0;
        const currAct = totals.activated || 0;

        const prev = prevRef.current;
        const timeNowStr = new Date().toISOString().substring(11, 19) + ' UTC';

        // Primeira carga: registra linha de base inicial
        if (prev.scanCycles === null) {
          prevRef.current = {
            scanCycles: currScan,
            evaluations: currEval,
            hdfD: currHdfD,
            candidates: currCand,
            armed: currArmed,
            activated: currAct,
          };
          if (data.errors > 0) {
            setStatusText('ERROR');
            setStatusColor('#ff5f72');
          } else if (data.stale > 0) {
            setStatusText('STALE');
            setStatusColor('#ff9f43');
          } else {
            setStatusText('LIVE');
            setStatusColor('#00f2fe');
          }
          return;
        }

        const deltaScan = currScan - prev.scanCycles;
        const deltaEval = currEval - prev.evaluations;
        const deltaHdfD = currHdfD - prev.hdfD;
        const deltaAct = currAct - prev.activated;

        // Atualizar estado de saúde visual
        if (data.errors > 0) {
          setStatusText('ERROR');
          setStatusColor('#ff5f72');
        } else if (data.stale > 0) {
          setStatusText('STALE');
          setStatusColor('#ff9f43');
        } else if (deltaEval > 0) {
          setStatusText('EVALUATION');
          setStatusColor('#21d68d');
        } else if (deltaScan > 0) {
          setStatusText('LIVE');
          setStatusColor('#00f2fe');
        } else {
          setStatusText('WAITING_NEW_CANDLE');
          setStatusColor('#8a99ad');
        }

        // Governança estrita das pulsações: APENAS quando deltas > 0!
        let targetLeds = 0;
        let targetColor = '#00f2fe';
        let pType = null;

        if (deltaAct > 0) {
          targetLeds = 12; // ACTIVATED -> 12 LEDs
          targetColor = '#ffb020';
          pType = 'ACTIVATED';
        } else if (currArmed > 0 && currAct === 0) {
          targetLeds = 11; // ARMED -> 11 LEDs
          targetColor = '#ffb020';
          pType = 'ARMED';
        } else if (deltaHdfD > 0) {
          targetLeds = 8; // HDF_D -> 8 LEDs
          targetColor = '#00e5ff';
          pType = 'HDF_D';
        } else if (deltaEval > 0) {
          targetLeds = 6; // NOVA VELA AVALIADA -> 6 LEDs
          targetColor = '#21d68d';
          pType = 'EVALUATION';
        } else if (deltaScan > 0) {
          targetLeds = 3; // SCAN REAL -> 3 LEDs
          targetColor = '#00f2fe';
          pType = 'SCAN';
        }

        if (targetLeds > 0) {
          setActiveLeds(targetLeds);
          setPulseColor(targetColor);
          setLastPulseType(pType);
          setLastPulseTime(timeNowStr);

          if (pulseTimerRef.current) clearTimeout(pulseTimerRef.current);
          pulseTimerRef.current = setTimeout(() => {
            if (isMounted) setActiveLeds(0);
          }, PULSE_DURATION_MS);
        }

        // Atualiza estado prévio para a próxima comparação
        prevRef.current = {
          scanCycles: currScan,
          evaluations: currEval,
          hdfD: currHdfD,
          candidates: currCand,
          armed: currArmed,
          activated: currAct,
        };
      } catch (err) {
        if (isMounted) {
          setStatusText('ERROR');
          setStatusColor('#ff5f72');
        }
      }
    }

    pollTelemetry();
    const interval = setInterval(pollTelemetry, 1500);
    return () => {
      isMounted = false;
      clearInterval(interval);
      if (pulseTimerRef.current) clearTimeout(pulseTimerRef.current);
    };
  }, []);

  async function togglePopover() {
    const nextOpen = !isPopoverOpen;
    setIsPopoverOpen(nextOpen);
    if (nextOpen) {
      try {
        const scData = await getShadowScanners();
        setScanners(scData?.scanners || []);
      } catch (err) {
        console.error('Erro ao carregar lista de scanners:', err);
      }
    }
  }

  const totals = telemetry?.totals || {};
  const xauusdScanners = (scanners || []).filter((s) => s.symbol === 'XAUUSD');
  const otherScanners = (scanners || []).filter((s) => s.symbol !== 'XAUUSD');

  return (
    <div className="hk-hdf-activity-meter-container" style={{ display: 'inline-flex', alignItems: 'center', position: 'relative' }}>
      {/* Visual Activity Meter Bar */}
      <button
        type="button"
        className="hk-hdf-meter-btn"
        onClick={togglePopover}
        title="Clique para abrir telemetria real do HDF Engine"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          background: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '4px',
          padding: '2px 8px',
          cursor: 'pointer',
          color: 'var(--hk-text-main)',
          fontSize: '11px',
          fontWeight: 600,
        }}
      >
        <span style={{ fontSize: '10px', color: 'var(--hk-text-muted)', letterSpacing: '0.5px' }}>
          MOTOR HDF
        </span>

        {/* LED VU Meter Bar (12 discrete segments) */}
        <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
          {Array.from({ length: TOTAL_LEDS }).map((_, idx) => {
            const isActive = idx < activeLeds;
            return (
              <span
                key={idx}
                style={{
                  width: '3px',
                  height: '10px',
                  borderRadius: '1px',
                  background: isActive ? pulseColor : 'rgba(255, 255, 255, 0.12)',
                  boxShadow: isActive ? `0 0 6px ${pulseColor}` : 'none',
                  transition: 'background 0.15s ease, box-shadow 0.15s ease',
                }}
              />
            );
          })}
        </div>

        {/* Status dot & text badge */}
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '10px', fontWeight: 700 }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: statusColor, boxShadow: `0 0 4px ${statusColor}` }} />
          <span style={{ color: statusColor }}>{statusText}</span>
        </div>
      </button>

      {/* Popover / Telemetry Panel Modal */}
      {isPopoverOpen && (
        <div
          className="hk-hdf-telemetry-popover"
          style={{
            position: 'absolute',
            bottom: '32px',
            left: '0',
            width: '380px',
            background: 'var(--hk-bg-panel, #0e131b)',
            border: '1px solid var(--hk-border, #1e293b)',
            borderRadius: '6px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
            zIndex: 9999,
            padding: '12px',
            fontSize: '11px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', borderBottom: '1px solid var(--hk-border)', paddingBottom: '6px' }}>
            <span style={{ fontWeight: 700, color: 'var(--hk-accent-cyan)' }}>⚡ TELEMETRIA HDF ENGINE</span>
            <div style={{ display: 'flex', gap: '4px' }}>
              <button
                type="button"
                className={`hk-pill-btn ${activeTab === 'RESUMO' ? 'active' : ''}`}
                style={{ fontSize: '9px', padding: '2px 6px' }}
                onClick={() => setActiveTab('RESUMO')}
              >
                RESUMO
              </button>
              <button
                type="button"
                className={`hk-pill-btn ${activeTab === 'SCANNERS' ? 'active' : ''}`}
                style={{ fontSize: '9px', padding: '2px 6px' }}
                onClick={() => setActiveTab('SCANNERS')}
              >
                SCANNERS ({telemetry?.registered || 39})
              </button>
              <button
                type="button"
                onClick={() => setIsPopoverOpen(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '14px', marginLeft: '4px' }}
              >
                ×
              </button>
            </div>
          </div>

          {activeTab === 'RESUMO' ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '6px', borderRadius: '4px' }}>
                <span style={{ color: 'var(--hk-text-muted)', display: 'block', fontSize: '9px' }}>SCANNERS REGISTRADOS</span>
                <span style={{ fontWeight: 700, fontSize: '12px', color: '#21d68d' }}>{telemetry?.registered || 39} / 39</span>
              </div>

              <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '6px', borderRadius: '4px' }}>
                <span style={{ color: 'var(--hk-text-muted)', display: 'block', fontSize: '9px' }}>CICLOS ACUMULADOS</span>
                <span style={{ fontWeight: 700, fontSize: '12px', color: '#00f2fe' }}>{totals.scan_cycles?.toLocaleString() || 0}</span>
              </div>

              <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '6px', borderRadius: '4px' }}>
                <span style={{ color: 'var(--hk-text-muted)', display: 'block', fontSize: '9px' }}>AVALIAÇÕES DE CANDLE</span>
                <span style={{ fontWeight: 700, fontSize: '12px', color: '#21d68d' }}>{totals.evaluations?.toLocaleString() || 0}</span>
              </div>

              <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '6px', borderRadius: '4px' }}>
                <span style={{ color: 'var(--hk-text-muted)', display: 'block', fontSize: '9px' }}>ÚLTIMO EVENTO VISUAL</span>
                <span style={{ fontWeight: 700, fontSize: '11px', color: pulseColor }}>{lastPulseType} ({lastPulseTime})</span>
              </div>

              <div style={{ gridColumn: 'span 2', background: 'rgba(255, 255, 255, 0.02)', padding: '6px', borderRadius: '4px' }}>
                <span style={{ color: 'var(--hk-text-muted)', display: 'block', fontSize: '9px', marginBottom: '4px' }}>FUNIL QUANTITATIVO HDF</span>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px' }}>
                  <span>HDF_D: <strong>{totals.hdf_d || 0}</strong></span>
                  <span>HDF_DV: <strong>{totals.hdf_dv || 0}</strong></span>
                  <span>HDF_DP: <strong>{totals.hdf_dp || 0}</strong></span>
                  <span>HDF_DVP: <strong>{totals.hdf_dvp || 0}</strong></span>
                </div>
              </div>

              <div style={{ gridColumn: 'span 2', background: 'rgba(255, 255, 255, 0.02)', padding: '6px', borderRadius: '4px', position: 'relative' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px' }}>
                  <span
                    onMouseEnter={() => setIsCandidateHovered(true)}
                    onMouseLeave={() => setIsCandidateHovered(false)}
                    style={{
                      cursor: 'pointer',
                      borderBottom: '1px dotted #00f2fe',
                      paddingBottom: '1px',
                    }}
                    title="Passe o mouse para ver a lista de candidatos reais"
                  >
                    CANDIDATOS: <strong style={{ color: '#00f2fe' }}>{totals.candidates || 0} 🛈</strong>
                  </span>
                  <span>ARMADO: <strong style={{ color: '#ffb020' }}>{totals.armed || 0}</strong></span>
                  <span>ATIVADO: <strong style={{ color: '#21d68d' }}>{totals.activated || 0}</strong></span>
                </div>

                {/* Popover de Hover dos Candidatos Reais */}
                {isCandidateHovered && (
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '26px',
                      left: '0',
                      width: '320px',
                      maxHeight: '220px',
                      overflowY: 'auto',
                      background: 'var(--hk-bg-panel, #0b0f19)',
                      border: '1px solid #00f2fe',
                      borderRadius: '6px',
                      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.7)',
                      padding: '8px',
                      zIndex: 10000,
                      fontSize: '10px',
                      color: 'var(--hk-text-main, #f8fafc)',
                    }}
                  >
                    <div style={{ fontWeight: 700, borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px', marginBottom: '6px', color: '#00f2fe' }}>
                      CANDIDATOS REAIS DO MOTOR ({totals.candidates || 0})
                    </div>

                    {!totals.candidate_items || totals.candidate_items.length === 0 ? (
                      <div style={{ color: '#8a99ad', fontStyle: 'italic', padding: '4px 0' }}>
                        Nenhum candidato no momento (Aguardando confluências).
                      </div>
                    ) : (
                      totals.candidate_items.map((item, idx) => {
                        const isBull = item.direction === 'BULLISH';
                        const dirColor = isBull ? '#21d68d' : '#ff5f72';
                        const arrow = isBull ? '▲' : '▼';
                        return (
                          <div
                            key={idx}
                            style={{
                              background: 'rgba(255, 255, 255, 0.03)',
                              border: '1px solid rgba(255, 255, 255, 0.06)',
                              borderRadius: '4px',
                              padding: '6px',
                              marginBottom: idx < totals.candidate_items.length - 1 ? '6px' : '0',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, marginBottom: '2px' }}>
                              <span>{item.symbol} · {item.timeframe}</span>
                              <span style={{ color: dirColor }}>
                                {item.direction} {arrow}
                              </span>
                            </div>
                            <div style={{ fontSize: '9px', color: '#8a99ad' }}>
                              Estágio: <strong style={{ color: '#00f2fe' }}>{item.stage}</strong>
                            </div>
                            {item.confluences && item.confluences.length > 0 && (
                              <div style={{ fontSize: '9px', color: '#cbd5e1', marginTop: '2px' }}>
                                Confluências: <span style={{ color: '#21d68d' }}>{item.confluences.join(' + ')}</span>
                              </div>
                            )}
                            {item.pending && item.pending.length > 0 && (
                              <div style={{ fontSize: '9px', color: '#ff9f43', marginTop: '1px' }}>
                                Pendente: {item.pending.join(', ')}
                              </div>
                            )}
                            <div style={{ fontSize: '8px', color: '#64748b', textAlign: 'right', marginTop: '3px' }}>
                              Atualizado: {item.updated_at}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '9px' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--hk-border)', color: 'var(--hk-text-muted)' }}>
                    <th style={{ padding: '4px' }}>SÍMBOLO</th>
                    <th style={{ padding: '4px' }}>TF</th>
                    <th style={{ padding: '4px' }}>ESTÁGIO</th>
                    <th style={{ padding: '4px' }}>STATUS</th>
                  </tr>
                </thead>
                <tbody>
                  {[...xauusdScanners, ...otherScanners].map((sc, i) => {
                    const isGold = sc.symbol === 'XAUUSD';
                    return (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', background: isGold ? 'rgba(255, 176, 32, 0.05)' : 'transparent' }}>
                        <td style={{ padding: '3px 4px', fontWeight: isGold ? 700 : 400, color: isGold ? '#ffb020' : 'inherit' }}>{sc.symbol}</td>
                        <td style={{ padding: '3px 4px' }}>{sc.timeframe}</td>
                        <td style={{ padding: '3px 4px' }}>{sc.last_result_stage || 'NONE'}</td>
                        <td style={{ padding: '3px 4px', color: sc.status === 'RUNNING' ? '#21d68d' : '#8a99ad' }}>{sc.status}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
