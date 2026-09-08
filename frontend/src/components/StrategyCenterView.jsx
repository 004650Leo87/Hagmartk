import React, { useEffect, useState } from 'react';
import { getOrbStatus } from '../services/api';

export default function StrategyCenterView() {
  const [orbStatus, setOrbStatus] = useState(null);

  useEffect(() => {
    let mounted = true;
    getOrbStatus().then((data) => {
      if (mounted) setOrbStatus(data);
    }).catch(() => {
      if (mounted) setOrbStatus(null);
    });
    return () => { mounted = false; };
  }, []);

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
              <code>d192dd... (Congelado)</code>
            </div>
          </div>
        </div>
      </div>

      {/* Universe Specification */}
      <div className="hk-card full-width">
        <div className="hk-card-header">
          <span className="hk-card-icon">🛡️</span>
          <h3>Shadow Universe Multi-Provider</h3>
        </div>
        <div className="hk-card-body">
          <p className="hk-text-secondary">
            O universo operacional &eacute; descoberto dinamicamente nas fontes MT5/Tickmill e Binance USD-M Futures e monitorado nos 8 timeframes aprovados (M5, M15, M30, H1, H2, H4, D1, W1), sem execu&ccedil;&atilde;o de ordens reais. O candidato matem&aacute;tico v1.0.0 permanece congelado.
          </p>
          <div className="hk-tags-cloud">
            {['MT5 / Tickmill', 'Binance USD-M Futures', '8 Timeframes', 'Shadow / Paper'].map((asset) => (
              <span key={asset} className="hk-tag-chip">
                {asset} (8 TFs)
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="hk-card full-width" style={{ marginTop: '16px' }}>
        <div className="hk-card-header">
          <span className="hk-card-icon">🧭</span>
          <h3>ORB — Opening Range 15M / Sinal 5M / Alvo 2R</h3>
        </div>
        <div className="hk-card-body">
          <p className="hk-text-secondary">
            Estratégia ORB v1.0.0 integrada ao motor quantitativo em estágio de validação. O núcleo de sinal, risco, execução de referência e estatísticas está congelado; operação real permanece bloqueada.
          </p>
          <div className="hk-grid-3">
            <div className="hk-param-row"><span>Faixa inicial:</span><strong>15 minutos</strong></div>
            <div className="hk-param-row"><span>Sinal:</span><strong>Fechamento M5 fora da faixa</strong></div>
            <div className="hk-param-row"><span>Alvo:</span><strong>2R fixo / 100%</strong></div>
            <div className="hk-param-row"><span>Risco:</span><strong>0,25% por oportunidade</strong></div>
            <div className="hk-param-row"><span>TradingView:</span><strong>ORB</strong></div>
            <div className="hk-param-row"><span>Ordens reais:</span><strong>NÃO</strong></div>
          </div>

          <div className="hk-param-row" style={{ marginTop: '10px' }}>
            <span>Estágio:</span>
            <strong>{orbStatus?.stage || 'VALIDATION'}</strong>
          </div>
          <div className="hk-param-row">
            <span>Perfis de sessão:</span>
            <strong>{orbStatus?.session_profiles_configured ?? 0}</strong>
          </div>
          <div className="hk-param-row">
            <span>Status prospectivo:</span>
            <strong>{orbStatus?.blocking_reason || 'EXPLICIT_SESSION_PROFILES_REQUIRED'}</strong>
          </div>
          <div className="hk-param-row">
            <span>Config Hash:</span>
            <code>{orbStatus?.config_hash ? `${orbStatus.config_hash.slice(0, 12)}...` : 'c1db74b8f238...'}</code>
          </div>
        </div>
      </div>

    </div>
  );
}
