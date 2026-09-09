import React, { useEffect, useMemo, useState } from 'react';
import { getCandles } from '../services/api';
import { prepareCandles } from '../chart/chartData';

const VIEW_W = 960;
const VIEW_H = 520;
const PAD = { left: 42, right: 92, top: 38, bottom: 54 };

function n(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function eventEpoch(value) {
  if (!value) return 0;
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? Math.floor(parsed / 1000) : 0;
}

function fmt(value) {
  if (!Number.isFinite(value)) return '—';
  if (Math.abs(value) >= 1000) return value.toFixed(2);
  if (Math.abs(value) >= 10) return value.toFixed(3);
  return value.toFixed(5).replace(/0+$/, '').replace(/\.$/, '');
}
function targetValues(alert) {
  return (alert?.targets || []).map((row) => n(row?.value)).filter(Boolean);
}

function useEvidenceCandles(alert) {
  const [candles, setCandles] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let active = true;
    if (!alert?.symbol) {
      setCandles([]);
      return undefined;
    }
    async function load() {
      setLoading(true);
      try {
        const response = await getCandles(alert.symbol, alert.timeframe || 'M5', 500, 0);
        if (active) setCandles(prepareCandles(response));
      } catch (err) {
        console.error('Falha ao carregar candles da evidência:', err);
        if (active) setCandles([]);
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [alert?.symbol, alert?.timeframe, alert?.event_time_utc]);
  return { candles, loading };
}
function selectWindow(candles, alert) {
  if (!candles.length) return [];
  const eventTs = eventEpoch(alert?.event_time_utc);
  let pivot = candles.length - 1;
  if (eventTs) {
    let min = Infinity;
    candles.forEach((candle, index) => {
      const diff = Math.abs(candle.time - eventTs);
      if (diff < min) {
        min = diff;
        pivot = index;
      }
    });
  }
  const from = Math.max(0, pivot - 58);
  const to = Math.min(candles.length, pivot + 16);
  const window = candles.slice(from, to);
  return window.length >= 30 ? window : candles.slice(-74);
}

function levelRows(alert) {
  const rows = [];
  const entry = n(alert?.entry);
  if (entry) rows.push({ key: 'entry', label: 'Entrada', value: entry, color: '#d7dde5' });
  (alert?.targets || []).forEach((target, index) => {
    const value = n(target?.value);
    if (value) rows.push({ key: `target-${index}`, label: target.label, value, color: '#36d887' });
  });
  const stop = n(alert?.stop);
  if (stop) rows.push({ key: 'stop', label: 'Stop', value: stop, color: '#ff5757' });
  return rows;
}
function buildGeometry(window, alert) {
  if (!window.length) return null;
  const evidence = alert?.evidence || {};
  const levels = levelRows(alert);
  const extra = [
    ...levels.map((row) => row.value),
    n(evidence.channel_high), n(evidence.channel_low), n(evidence.expansion),
    n(evidence.range_high), n(evidence.range_low),
  ].filter(Boolean);
  let lo = Math.min(...window.map((c) => c.low), ...extra);
  let hi = Math.max(...window.map((c) => c.high), ...extra);
  const span = Math.max(hi - lo, Math.abs(hi) * 0.001, 1e-8);
  lo -= span * 0.12;
  hi += span * 0.12;
  const innerW = VIEW_W - PAD.left - PAD.right;
  const innerH = VIEW_H - PAD.top - PAD.bottom;
  const step = innerW / Math.max(window.length, 1);
  const x = (index) => PAD.left + step * index + step / 2;
  const y = (price) => PAD.top + ((hi - price) / (hi - lo)) * innerH;
  const nearestIndex = (timeValue) => {
    const ts = eventEpoch(timeValue);
    if (!ts) return -1;
    let best = -1; let diff = Infinity;
    window.forEach((candle, index) => {
      const d = Math.abs(candle.time - ts);
      if (d < diff) { diff = d; best = index; }
    });
    return best;
  };
  return { evidence, levels, lo, hi, innerW, innerH, step, x, y, nearestIndex };
}
export default function EvidenceChart({ alert }) {
  const { candles, loading } = useEvidenceCandles(alert);
  const window = useMemo(() => selectWindow(candles, alert), [candles, alert]);
  const g = useMemo(() => buildGeometry(window, alert), [window, alert]);

  if (!alert) {
    return <div className="ev-chart-empty">Selecione uma ocorrência para abrir a evidência.</div>;
  }
  if (loading && !window.length) {
    return <div className="ev-chart-empty">Carregando evidência de mercado...</div>;
  }
  if (!g || !window.length) {
    return <div className="ev-chart-empty">Candles não disponíveis para esta ocorrência.</div>;
  }

  const eventIndex = Math.max(0, g.nearestIndex(alert.event_time_utc));
  const isBuy = alert.direction === 'COMPRA';
  const highZone = n(g.evidence.channel_high);
  const lowZone = n(g.evidence.channel_low);
  const rangeHigh = n(g.evidence.range_high);
  const rangeLow = n(g.evidence.range_low);
  const p1Index = g.nearestIndex(g.evidence.pivot_1_time);
  const p2Index = g.nearestIndex(g.evidence.pivot_2_time);
  const refIndex = g.nearestIndex(g.evidence.ref_time_start);

  return (
    <div className="ev-chart-wrap">
      <svg className="ev-chart-svg" viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} role="img">
        <defs>
          <linearGradient id="zoneFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#c9d1da" stopOpacity="0.12" />
            <stop offset="1" stopColor="#84909d" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width={VIEW_W} height={VIEW_H} rx="12" fill="#071017" />
        {[0, 1, 2, 3, 4, 5].map((i) => {
          const yy = PAD.top + (g.innerH * i) / 5;
          const price = g.hi - ((g.hi - g.lo) * i) / 5;
          return (
            <g key={`h-${i}`}>
              <line x1={PAD.left} y1={yy} x2={VIEW_W - PAD.right} y2={yy} stroke="#22303a" strokeWidth="1" />
              <text x={VIEW_W - PAD.right + 10} y={yy + 4} fill="#8593a0" fontSize="12">{fmt(price)}</text>
            </g>
          );
        })}
        {[0, 1, 2, 3, 4, 5].map((i) => {
          const index = Math.min(window.length - 1, Math.floor((window.length - 1) * i / 5));
          const xx = g.x(index);
          const d = new Date(window[index].time * 1000);
          return (
            <g key={`v-${i}`}>
              <line x1={xx} y1={PAD.top} x2={xx} y2={VIEW_H - PAD.bottom} stroke="#15242e" strokeWidth="1" />
              <text x={xx} y={VIEW_H - 18} textAnchor="middle" fill="#7f8b96" fontSize="12">
                {d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' })}
              </text>
            </g>
          );
        })}
        <text x={VIEW_W / 2} y={VIEW_H / 2} textAnchor="middle" fill="#ffffff" opacity="0.055" fontSize="58" fontWeight="800">HAGMARTK</text>
        {window.map((candle, index) => {
          const xx = g.x(index);
          const bodyW = Math.max(2.2, g.step * 0.58);
          const up = candle.close >= candle.open;
          const trigger = alert.strategy_key === 'DVP' && index === eventIndex;
          let color = up ? '#22c987' : '#ff5c5c';
          if (trigger) color = isBuy ? '#ffffff' : '#ffd84d';
          const yOpen = g.y(candle.open);
          const yClose = g.y(candle.close);
          return (
            <g key={candle.time}>
              <line x1={xx} y1={g.y(candle.high)} x2={xx} y2={g.y(candle.low)} stroke={color} strokeWidth="1.2" />
              <rect x={xx - bodyW / 2} y={Math.min(yOpen, yClose)} width={bodyW}
                height={Math.max(1.4, Math.abs(yClose - yOpen))} fill={color} rx="0.6" />
            </g>
          );
        })}
        {window.map((candle, index) => {
          const maxRange = Math.max(...window.map((c) => c.high - c.low), 1e-9);
          const volumeProxy = Math.min(1, Math.max(0.15, (candle.high - candle.low) / maxRange));
          const barH = 34 * volumeProxy;
          const xx = g.x(index);
          return <rect key={`vol-${candle.time}`} x={xx - Math.max(1, g.step * 0.25)} y={VIEW_H - PAD.bottom - barH}
            width={Math.max(2, g.step * 0.5)} height={barH} fill={candle.close >= candle.open ? '#167e61' : '#873b42'} opacity="0.62" />;
        })}
        {alert.strategy_key === 'TC' && highZone && lowZone && (
          <g>
            <rect x={g.x(refIndex >= 0 ? refIndex : 8)} y={g.y(highZone)}
              width={Math.max(120, g.x(eventIndex) - g.x(refIndex >= 0 ? refIndex : 8))}
              height={Math.abs(g.y(lowZone) - g.y(highZone))} fill="url(#zoneFill)"
              stroke="#c8d0d8" strokeDasharray="7 6" opacity="0.9" />
            <text x={(g.x(refIndex >= 0 ? refIndex : 8) + g.x(eventIndex)) / 2} y={(g.y(highZone) + g.y(lowZone)) / 2 - 4}
              textAnchor="middle" fill="#e3e8ed" fontSize="13" fontWeight="700">ZONA NEUTRA</text>
            <text x={(g.x(refIndex >= 0 ? refIndex : 8) + g.x(eventIndex)) / 2} y={(g.y(highZone) + g.y(lowZone)) / 2 + 14}
              textAnchor="middle" fill="#9ca8b3" fontSize="11">CANAL NEUTRO</text>
          </g>
        )}
        {alert.strategy_key === 'ORB' && rangeHigh && rangeLow && (
          <g>
            <rect x={PAD.left + g.step * 6} y={g.y(rangeHigh)}
              width={Math.max(105, g.x(eventIndex) - (PAD.left + g.step * 6))}
              height={Math.abs(g.y(rangeLow) - g.y(rangeHigh))}
              fill="#3b82f6" fillOpacity="0.10" stroke="#62b0ff" strokeWidth="1.5" />
            <text x={PAD.left + g.step * 9} y={(g.y(rangeHigh) + g.y(rangeLow)) / 2}
              fill="#8ec8ff" fontSize="13" fontWeight="700">OPENING RANGE</text>
          </g>
        )}
        {alert.strategy_key === 'TC' && (n(g.evidence.c1_mid) || n(g.evidence.expansion)) && (
          <g>
            {n(g.evidence.c1_mid) && (
              <>
                <line x1={g.x(refIndex >= 0 ? refIndex : Math.max(0, eventIndex - 12))}
                  y1={g.y(n(g.evidence.c1_mid))}
                  x2={g.x(Math.max(eventIndex, refIndex >= 0 ? refIndex + 1 : eventIndex))}
                  y2={g.y(n(g.evidence.c1_mid))}
                  stroke="#d8ae4b" strokeWidth="1.4" strokeDasharray="6 5" opacity="0.9" />
                <text x={g.x(refIndex >= 0 ? refIndex : Math.max(0, eventIndex - 12)) + 6}
                  y={g.y(n(g.evidence.c1_mid)) - 7} fill="#e2bd62" fontSize="14" fontWeight="800">C1</text>
              </>
            )}
            {n(g.evidence.mid_line50) && g.evidence.is_split_active && (
              <>
                <line x1={g.x(refIndex >= 0 ? refIndex : 0)} y1={g.y(n(g.evidence.mid_line50))}
                  x2={g.x(eventIndex)} y2={g.y(n(g.evidence.mid_line50))}
                  stroke="#f2d04f" strokeWidth="1.3" strokeDasharray="3 5" />
                <text x={g.x(eventIndex) - 5} y={g.y(n(g.evidence.mid_line50)) - 6}
                  textAnchor="end" fill="#f2d04f" fontSize="11">DIVISÃO 50%</text>
              </>
            )}
            {n(g.evidence.expansion) && (
              <>
                <line x1={g.x(Math.max(0, eventIndex - 4))} y1={g.y(n(g.evidence.expansion))}
                  x2={VIEW_W - PAD.right - 4} y2={g.y(n(g.evidence.expansion))}
                  stroke="#d6a43d" strokeWidth="2" />
                <text x={VIEW_W - PAD.right - 10} y={g.y(n(g.evidence.expansion)) - 7}
                  textAnchor="end" fill="#dcb65c" fontSize="12" fontWeight="800">EXPANSÃO</text>
              </>
            )}
          </g>
        )}
        {alert.strategy_key === 'DVP' && p1Index >= 0 && p2Index >= 0 && (
          <g>
            <line x1={g.x(p1Index)} y1={g.y(n(g.evidence.pivot_1_price) || window[p1Index].low)}
              x2={g.x(p2Index)} y2={g.y(n(g.evidence.pivot_2_price) || window[p2Index].low)}
              stroke="#35b9ff" strokeWidth="2.2" />
            <text x={(g.x(p1Index) + g.x(p2Index)) / 2} y={Math.min(g.y(window[p1Index].low), g.y(window[p2Index].low)) + 30}
              textAnchor="middle" fill="#46c4ff" fontSize="12" fontWeight="700">DIVERGÊNCIA DVP</text>
          </g>
        )}
        {alert.strategy_key === 'DVP' && (
          <g>
            <line x1={g.x(eventIndex) - 40} y1={g.y(window[eventIndex]?.high || window[0].high) - 30}
              x2={g.x(eventIndex)} y2={g.y(window[eventIndex]?.high || window[0].high) - 3}
              stroke="#f3f5f7" strokeWidth="1.5" />
            <text x={g.x(eventIndex) - 44} y={g.y(window[eventIndex]?.high || window[0].high) - 34}
              textAnchor="middle" fill="#f5f7fa" fontSize="12" fontWeight="700">CANDLE GATILHO</text>
          </g>
        )}
        {alert.strategy_key === 'ORB' && (
          <g>
            <line x1={g.x(eventIndex) - 34} y1={g.y(window[eventIndex]?.high || window[0].high) - 28}
              x2={g.x(eventIndex)} y2={g.y(window[eventIndex]?.high || window[0].high) - 3}
              stroke="#f5f7fa" strokeWidth="1.5" />
            <text x={g.x(eventIndex) - 40} y={g.y(window[eventIndex]?.high || window[0].high) - 33}
              textAnchor="middle" fill="#f5f7fa" fontSize="12" fontWeight="700">ROMPIMENTO</text>
          </g>
        )}
        {g.levels.map((row) => {
          const yy = g.y(row.value);
          const dash = row.key === 'entry' ? '8 6' : row.key === 'stop' ? '0' : '0';
          return (
            <g key={row.key}>
              <line x1={g.x(Math.max(0, eventIndex - 4))} y1={yy} x2={VIEW_W - PAD.right - 4} y2={yy}
                stroke={row.color} strokeWidth={row.key === 'entry' ? 1.6 : 1.8} strokeDasharray={dash} opacity="0.95" />
              <text x={VIEW_W - PAD.right - 10} y={yy - 6} textAnchor="end" fill={row.color}
                fontSize="12" fontWeight="800">{row.label} ({fmt(row.value)})</text>
            </g>
          );
        })}
        <text x={PAD.left + 6} y={PAD.top + 18} fill="#e8edf2" fontSize="14" fontWeight="800">
          {alert.symbol} · {alert.timeframe || 'M5'} · EVIDÊNCIA
        </text>
        <text x={VIEW_W - PAD.right - 12} y={VIEW_H - 18} textAnchor="end" fill="#6b7782" fontSize="10">
          HAGMARTK · SHADOW / SIMULAÇÃO
        </text>
      </svg>
    </div>
  );
}
