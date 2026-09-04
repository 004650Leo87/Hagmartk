import React, { useEffect, useState } from 'react';
import HdfActivityMeter from './HdfActivityMeter';

export default function BottomStatusBar({
  mt5Connected,
  operationalCount = 0,
  totalCount = 104,
  lastActivity,
}) {
  const [utcTime, setUtcTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toISOString().substring(11, 19) + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <footer className="hk-statusbar-v3">
      <div className="hk-statusbar-strip">
        <div className="hk-statusbar-left">
          <div className={`hk-status-item-compact ${mt5Connected ? 'success' : 'error'}`}>
            <span className="hk-status-dot-sm" />
            <span>MT5: {mt5Connected ? 'CONECTADO' : 'DESCONECTADO'}</span>
          </div>
          <div className="hk-statusbar-sep">│</div>
          <div className="hk-status-item-compact info">
            <span>SHADOW: {operationalCount}/{totalCount}</span>
          </div>
          <div className="hk-statusbar-sep">│</div>
          <HdfActivityMeter />
          <div className="hk-statusbar-sep">│</div>
          <div className="hk-status-item-compact warning">
            <span>🔒 EXECUTION OFF</span>
          </div>
        </div>
        <div className="hk-statusbar-right">
          {lastActivity && <span className="hk-status-subtext">Varredura: {lastActivity}</span>}
          <span className="hk-status-time">{utcTime}</span>
        </div>
      </div>
    </footer>
  );
}
