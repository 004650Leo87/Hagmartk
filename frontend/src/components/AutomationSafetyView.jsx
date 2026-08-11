import React from 'react';

export default function AutomationSafetyView() {
  return (
    <div className="hk-view-container">
      <div className="hk-view-header">
        <div>
          <h2 className="hk-view-title">AUTOMAÇÃO & PAINEL DE SEGURANÇA</h2>
          <p className="hk-view-subtitle">Monitoramento de travas de execução e políticas de publicação externa.</p>
        </div>
      </div>

      <div className="hk-grid-2">
        <div className="hk-card">
          <div className="hk-card-header">
            <span className="hk-card-icon">🔒</span>
            <h3>Status das Travas de Execução</h3>
          </div>
          <div className="hk-card-body">
            <div className="hk-safety-row">
              <div>
                <strong>Negociação no Broker (Broker Trading)</strong>
                <p>Execução de ordens reais de compra/venda na corretora.</p>
              </div>
              <span className="hk-badge-disabled">DISABLED (OFF)</span>
            </div>

            <div className="hk-safety-row">
              <div>
                <strong>Promoção Automática (Auto-Promotion)</strong>
                <p>Promoção automática de setups para conta real.</p>
              </div>
              <span className="hk-badge-disabled">DISABLED (OFF)</span>
            </div>

            <div className="hk-safety-row">
              <div>
                <strong>Publicação Externa (Telegram / WhatsApp)</strong>
                <p>Envio de alertas para canais e redes externas.</p>
              </div>
              <span className="hk-badge-disabled">DISABLED (OFF)</span>
            </div>

            <div className="hk-safety-row">
              <div>
                <strong>Otimização Dinâmica de Parâmetros</strong>
                <p>Alteração automática de parâmetros RSI / pivôs.</p>
              </div>
              <span className="hk-badge-disabled">DISABLED (OFF)</span>
            </div>
          </div>
        </div>

        <div className="hk-card">
          <div className="hk-card-header">
            <span className="hk-card-icon">🛡️</span>
            <h3>Modo de Operação Atual</h3>
          </div>
          <div className="hk-card-body">
            <div className="hk-banner-success">
              ✓ SHADOW MODE PROSPECTIVO ATIVO <br />
              O sistema opera exclusivamente em ambiente de observação estatística continuada (33/39 combinações ativas).
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
