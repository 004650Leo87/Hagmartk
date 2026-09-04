import React, { useEffect, useState } from 'react';
import { getShadowCoverage, getTelegramNotificationStatus } from '../services/api';

export default function AutomationSafetyView() {
  const [coverage, setCoverage] = useState(null);
  const [telegram, setTelegram] = useState(null);

  useEffect(() => {
    let mounted = true;
    const refresh = async () => {
      const [coverageResult, telegramResult] = await Promise.allSettled([
        getShadowCoverage(),
        getTelegramNotificationStatus(),
      ]);
      if (!mounted) return;
      if (coverageResult.status === 'fulfilled') setCoverage(coverageResult.value);
      if (telegramResult.status === 'fulfilled') setTelegram(telegramResult.value);
    };
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const telegramReady = telegram?.ready === true;
  const active = coverage?.active ?? 0;
  const registered = coverage?.registered ?? 104;

  return (
    <div className="hk-view-container">
      <div className="hk-view-header"><div>
        <h2 className="hk-view-title">AUTOMA&Ccedil;&Atilde;O &amp; PAINEL DE SEGURAN&Ccedil;A</h2>
        <p className="hk-view-subtitle">Monitoramento de travas de execu&ccedil;&atilde;o e publica&ccedil;&atilde;o externa.</p>
      </div></div>

      <div className="hk-grid-2">
        <div className="hk-card">
          <div className="hk-card-header"><span className="hk-card-icon">&#128274;</span><h3>Status das Travas de Execu&ccedil;&atilde;o</h3></div>
          <div className="hk-card-body">
            <div className="hk-safety-row"><div>
              <strong>Negocia&ccedil;&atilde;o no Broker (Broker Trading)</strong><p>Execu&ccedil;&atilde;o de ordens reais de compra/venda na corretora.</p>
            </div><span className="hk-badge-disabled">DISABLED (OFF)</span></div>

            <div className="hk-safety-row"><div>
              <strong>Promo&ccedil;&atilde;o Autom&aacute;tica (Auto-Promotion)</strong><p>Promo&ccedil;&atilde;o autom&aacute;tica de setups para conta real.</p>
            </div><span className="hk-badge-disabled">DISABLED (OFF)</span></div>

            <div className="hk-safety-row"><div>
              <strong>Alertas Telegram</strong><p>Publica&ccedil;&atilde;o externa apenas de eventos SHADOW / PAPER.</p>
            </div><span style={{ color: telegramReady ? '#34d399' : '#f59e0b', fontWeight: 700, fontSize: '11px' }}>
              {telegramReady ? 'ENABLED (PAPER)' : 'INDISPONIVEL'}
            </span></div>

            <div className="hk-safety-row"><div>
              <strong>WhatsApp</strong><p>Canal externo ainda n&atilde;o habilitado para o Shadow.</p>
            </div><span className="hk-badge-disabled">DISABLED (OFF)</span></div>

            <div className="hk-safety-row"><div>
              <strong>Otimiza&ccedil;&atilde;o Din&acirc;mica de Par&acirc;metros</strong><p>Altera&ccedil;&atilde;o autom&aacute;tica do candidato congelado.</p>
            </div><span className="hk-badge-disabled">DISABLED (OFF)</span></div>
          </div>
        </div>

        <div className="hk-card">
          <div className="hk-card-header"><span className="hk-card-icon">&#128737;</span><h3>Modo de Opera&ccedil;&atilde;o Atual</h3></div>
          <div className="hk-card-body"><div className="hk-banner-success">
            &#10003; SHADOW MODE PROSPECTIVO ATIVO <br />
            Observa&ccedil;&atilde;o real de mercado em {registered} combina&ccedil;&otilde;es configuradas ({active}/{registered} operacionais no &uacute;ltimo estado).<br />
            &#128274; Execu&ccedil;&atilde;o de ordens reais permanece bloqueada.
          </div></div>
        </div>
      </div>
    </div>
  );
}
