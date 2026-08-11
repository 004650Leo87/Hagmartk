import React from 'react';

export default function BacktestView() {
  return (
    <div className="hk-view-container">
      <div className="hk-view-header">
        <div>
          <h2 className="hk-view-title">BACKTEST LAB — SIMULAÇÃO HISTÓRICA HDF</h2>
          <p className="hk-view-subtitle">Módulo de simulações históricas auditadas isoladas em desenvolvimento.</p>
        </div>
        <span className="hk-popover-badge degraded">EM DESENVOLVIMENTO</span>
      </div>

      <div className="hk-card full-width">
        <div className="hk-card-header">
          <span className="hk-card-icon">🛠</span>
          <h3>MÓDULO DE BACKTEST HISTÓRICO</h3>
        </div>
        <div className="hk-card-body" style={{ textAlign: 'center', padding: '40px 20px' }}>
          <div className="hk-empty-icon" style={{ fontSize: '36px', marginBottom: '12px' }}>🚧</div>
          <h4 style={{ fontSize: '15px', color: 'var(--hk-text-primary)', marginBottom: '8px' }}>
            RECURSO EM DESENVOLVIMENTO — NÃO OPERACIONAL
          </h4>
          <p style={{ fontSize: '12px', color: 'var(--hk-text-muted)', marginBottom: '20px', maxWidth: '520px', margin: '0 auto 20px auto', lineHeight: '1.6' }}>
            O motor de backtest histórico estrito está em fase de auditoria arquitetural. Para evitar simulações fictícias ou visualizações estimadas, a execução de novos backtests está temporariamente desativada nesta versão.
          </p>
          <button
            type="button"
            className="hk-topbar-action-btn"
            disabled
            style={{
              margin: '0 auto',
              padding: '8px 20px',
              backgroundColor: 'var(--hk-bg-surface)',
              color: 'var(--hk-text-muted)',
              border: '1px solid var(--hk-border-base)',
              cursor: 'not-allowed',
              opacity: 0.6,
            }}
          >
            🔒 SIMULAÇÃO HISTÓRICA INDISPONÍVEL
          </button>
        </div>
      </div>
    </div>
  );
}
