import React from 'react';

export default function AiInsightsView() {
  return (
    <div className="hk-view-container">
      <div className="hk-view-header">
        <div>
          <h2 className="hk-view-title">IA HAGMARTK — EXPLICAÇÃO DETERMINÍSTICA & DIAGNÓSTICO</h2>
          <p className="hk-view-subtitle">Interpretação e explicabilidade baseada em regras determinísticas locais sem APIs pagas ou side-effects.</p>
        </div>
      </div>

      <div className="hk-grid-2">
        <div className="hk-card">
          <div className="hk-card-header">
            <span className="hk-card-icon">🧠</span>
            <h3>Recursos Ativos na V1</h3>
          </div>
          <div className="hk-card-body">
            <div className="hk-check-list">
              <div className="hk-check-item active">✓ Explicação humana de reason codes do HDF em Português</div>
              <div className="hk-check-item active">✓ Valoração determinística de maturidade de evidência</div>
              <div className="hk-check-item active">✓ Rastreamento de contradições em dados de mercado</div>
              <div className="hk-check-item active">✓ Diagnósticos de integridade do pipeline e conexões MT5</div>
            </div>
          </div>
        </div>

        <div className="hk-card">
          <div className="hk-card-header">
            <span className="hk-card-icon">🔒</span>
            <h3>Travas de Segurança da IA</h3>
          </div>
          <div className="hk-card-body">
            <div className="hk-check-list">
              <div className="hk-check-item warning">⚠ A IA NÃO pode alterar parâmetros congelados da estratégia HDF</div>
              <div className="hk-check-item warning">⚠ A IA NÃO pode enviar ordens reais ou modificar posições no broker</div>
              <div className="hk-check-item warning">⚠ A IA NÃO utiliza modelos gerativos externos que causem alucinações</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
