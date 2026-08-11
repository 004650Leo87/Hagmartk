import React from 'react';

export default function StrategyCenterView() {
  return (
    <div className="hk-view-container">
      <div className="hk-view-header">
        <div>
          <h2 className="hk-view-title">ESTRATÉGIA HDF — HAGMARTK DIVERGENCE FLOW</h2>
          <p className="hk-view-subtitle">Contrato matemático estatisticamente congelado e validado em Fase 4C-A.2.</p>
        </div>
        <div className="hk-badge-frozen">🔒 CONTRATO CONGELADO v1.0.0</div>
      </div>

      <div className="hk-grid-3">
        <div className="hk-card">
          <div className="hk-card-header">
            <span className="hk-card-icon">📈</span>
            <h3>Divergência & Indicadores</h3>
          </div>
          <div className="hk-card-body">
            <div className="hk-param-row">
              <span>RSI Oscilador:</span>
              <strong>Wilder RSI (14)</strong>
            </div>
            <div className="hk-param-row">
              <span>Detecção de Pivôs:</span>
              <strong>Left=2, Right=2</strong>
            </div>
            <div className="hk-param-row">
              <span>Distância de Pivôs:</span>
              <strong>5 a 50 barras</strong>
            </div>
            <div className="hk-param-row">
              <span>Tipo de Divergência:</span>
              <strong>Regular Altista / Baixista</strong>
            </div>
          </div>
        </div>

        <div className="hk-card">
          <div className="hk-card-header">
            <span className="hk-card-icon">⚡</span>
            <h3>Filtro de Volume & Gatilho</h3>
          </div>
          <div className="hk-card-body">
            <div className="hk-param-row">
              <span>Filtro de Volume:</span>
              <strong>Relativo MA20 ≥ 1.0x</strong>
            </div>
            <div className="hk-param-row">
              <span>Gatilho de Ativação:</span>
              <strong>NEXT_BAR Policy</strong>
            </div>
            <div className="hk-param-row">
              <span>Padrão de Reversão:</span>
              <strong>ReversalPatternDetector</strong>
            </div>
            <div className="hk-param-row">
              <span>Janela de Ativação:</span>
              <strong>Máximo 5 barras</strong>
            </div>
          </div>
        </div>

        <div className="hk-card">
          <div className="hk-card-header">
            <span className="hk-card-icon">🎯</span>
            <h3>Gestão de Risco & Alvo</h3>
          </div>
          <div className="hk-card-body">
            <div className="hk-param-row">
              <span>Stop Loss:</span>
              <strong>Stop Estrutural de Pivô</strong>
            </div>
            <div className="hk-param-row">
              <span>Política de Saída:</span>
              <strong>EXIT_2R (Alvo Fixo 2:1)</strong>
            </div>
            <div className="hk-param-row">
              <span>Candidate ID:</span>
              <code>hdf_dvp_exit_2r</code>
            </div>
            <div className="hk-param-row">
              <span>Parameter Hash:</span>
              <code>3bf74a... (Congelado)</code>
            </div>
          </div>
        </div>
      </div>

      {/* Universe Specification */}
      <div className="hk-card full-width">
        <div className="hk-card-header">
          <span className="hk-card-icon">🛡️</span>
          <h3>Shadow Universe (39 Combinações)</h3>
        </div>
        <div className="hk-card-body">
          <p className="hk-text-secondary">
            O Shadow Universe é imutável e composto por 13 ativos e 3 timeframes (M15, H1, H4). As 39 combinações são observadas prospectivamente sem qualquer execução de ordens reais.
          </p>
          <div className="hk-tags-cloud">
            {['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCHF', 'USDCAD', 'NZDUSD', 'EURJPY', 'GBPJPY', 'XAUUSD', 'XAGUSD', 'BTCUSD', 'ETHUSD'].map((asset) => (
              <span key={asset} className="hk-tag-chip">
                {asset} (M15/H1/H4)
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
