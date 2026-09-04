import { createPortal } from 'react-dom';
import { useEffect, useRef } from 'react';

const TOAST_STATES_WITH_NOTIFICATION = new Set([
  'HDF_DVP', 'ARMED', 'ACTIVATED', 'TARGET_2R', 'STOPPED', 'EXPIRED', 'INVALIDATED', 'MILESTONE_1R'
]);

const DIRECTION_LABELS = {
  BULLISH: 'COMPRA',
  BEARISH: 'VENDA',
};

const STATE_LABELS = {
  HDF_DVP: 'EVIDÊNCIA HDF_DVP CONFIRMADA',
  ARMED: 'CONFIGURAÇÃO ARMADA',
  ACTIVATED: 'ATIVAÇÃO OBSERVADA',
  TARGET_2R: 'OBJETIVO 2R ATINGIDO',
  STOPPED: 'ENCERRADO NO STOP',
  EXPIRED: 'SETUP EXPIRADO',
  INVALIDATED: 'SETUP INVALIDADO',
  MILESTONE_1R: 'MILESTONE 1R ATINGIDO',
};

function HdfToast({ toast, onDismiss, onNavigate }) {
  const timerRef = useRef(null);

  useEffect(() => {
    timerRef.current = setTimeout(() => {
      onDismiss(toast.id);
    }, 8000);
    return () => clearTimeout(timerRef.current);
  }, [toast.id, onDismiss]);

  const isBullish = toast.direction === 'BULLISH';
  const stateLabel = STATE_LABELS[toast.status_code] || toast.status_code;
  const dirLabel = DIRECTION_LABELS[toast.direction] || toast.direction;

  return (
    <div className={`hdf-toast ${isBullish ? 'bullish' : 'bearish'}`} role="alert" aria-live="polite">
      <div className="hdf-toast-header">
        <div className="hdf-toast-title">
          <span className="hdf-toast-strategy">HDF</span>
          <span className="hdf-toast-sep">•</span>
          <strong className="hdf-toast-symbol">{toast.symbol}</strong>
          <span className="hdf-toast-sep">•</span>
          <span className="hdf-toast-tf">{toast.timeframe}</span>
        </div>
        <div className="hdf-toast-badges">
          <span className="hdf-toast-badge shadow-badge">SHADOW</span>
          <span className={`hdf-toast-badge dir-badge ${isBullish ? 'buy' : 'sell'}`}>{dirLabel}</span>
        </div>
        <button type="button" className="hdf-toast-close" onClick={() => onDismiss(toast.id)} aria-label="Fechar">×</button>
      </div>

      <div className="hdf-toast-body">
        <span className="hdf-toast-state">{stateLabel}</span>
        {toast.status_code === 'HDF_DVP' && (
          <span className="hdf-toast-time">Vol {Number(toast.relative_volume || 0).toFixed(2)}x • {toast.pattern_type || 'Padrão confirmado'}</span>
        )}
        {toast.event_time && (
          <span className="hdf-toast-time">{new Date(toast.event_time).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}</span>
        )}
      </div>

      <button
        type="button"
        className="hdf-toast-action"
        onClick={() => onNavigate(toast)}
      >
        VER ANÁLISE
      </button>

      <div className="hdf-toast-progress">
        <div className="hdf-toast-progress-bar" style={{ animationDuration: '8s' }} />
      </div>
    </div>
  );
}

export default function HdfToastStack({ toasts, onDismiss, onNavigate }) {
  if (!toasts || toasts.length === 0) return null;

  return createPortal(
    <div className="hdf-toast-stack" role="region" aria-label="Alertas HDF Shadow">
      {toasts.slice(0, 4).map((toast) => (
        <HdfToast
          key={toast.id}
          toast={toast}
          onDismiss={onDismiss}
          onNavigate={onNavigate}
        />
      ))}
    </div>,
    document.body
  );
}

export { TOAST_STATES_WITH_NOTIFICATION };
