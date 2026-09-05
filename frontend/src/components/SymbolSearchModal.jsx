import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { getMarketCatalog } from '../services/api';

export default function SymbolSearchModal({
  symbols = [],
  watchlist = [],
  onSelectSymbol,
  onAdd,
  onClose,
}) {
  const [catalog, setCatalog] = useState(symbols);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(symbols.length === 0);

  useEffect(() => {
    if (symbols.length === 0) {
      getMarketCatalog()
        .then((res) => setCatalog(res || []))
        .catch(() => setCatalog([
          { symbol: 'XAUUSD', description: 'Gold vs US Dollar', category: 'METALS' },
          { symbol: 'EURUSD', description: 'Euro vs US Dollar', category: 'FOREX' },
          { symbol: 'GBPUSD', description: 'Great Britain Pound vs US Dollar', category: 'FOREX' },
          { symbol: 'USDJPY', description: 'US Dollar vs Japanese Yen', category: 'FOREX' },
          { symbol: 'BTCUSD', description: 'Bitcoin vs US Dollar', category: 'CRYPTO' },
        ]))
        .finally(() => setLoading(false));
    }
  }, [symbols]);

  const filtered = catalog.filter((item) => {
    const q = query.trim().toLowerCase();
    const sym = (item.symbol || item.name || item || '').toLowerCase();
    const desc = (item.description || '').toLowerCase();
    return !q || sym.includes(q) || desc.includes(q);
  });

  return createPortal(
    <div className="hk-drawer-overlay" onClick={onClose} style={{ zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="hk-card" onClick={(e) => e.stopPropagation()} style={{ width: '520px', maxHeight: '80vh', display: 'flex', flexDirection: 'column', padding: '20px', gap: '14px', backgroundColor: 'var(--hk-bg-surface-elevated)', border: '1px solid var(--hk-border-base)', boxShadow: 'var(--hk-shadow-lg)' }}>
        <div className="hk-card-header" style={{ justifyContent: 'space-between', borderBottom: '1px solid var(--hk-border-subdued)', paddingBottom: '10px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--hk-text-primary)' }}>🔍 BUSCAR ATIVO NO CATÁLOGO</h3>
          <button type="button" className="hk-close-btn" onClick={onClose}>×</button>
        </div>

        <input
          type="text"
          className="hk-search-input"
          style={{ width: '100%', padding: '10px 14px', fontSize: '13px' }}
          placeholder="Digite o código ou descrição (ex: EURUSD, XAUUSD, BTCUSDT)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '360px', paddingRight: '4px' }}>
          {loading ? (
            <div className="hk-empty">Carregando catálogo HAGMARTK (MT5 + Binance Futures)...</div>
          ) : filtered.length === 0 ? (
            <div className="hk-empty">Nenhum ativo encontrado para "{query}".</div>
          ) : (
            filtered.map((item) => {
              const sym = item.symbol || item.name || item;
              return (
                <div
                  key={sym}
                  className="hk-watchlist-item"
                  style={{ padding: '10px 12px' }}
                  onClick={() => {
                    if (onSelectSymbol) onSelectSymbol(sym);
                    if (onAdd) onAdd(sym);
                    onClose();
                  }}
                >
                  <div className="hk-wl-col-symbol">
                    <strong className="hk-wl-symbol" style={{ fontSize: '14px' }}>{sym}</strong>
                    <span className="hk-wl-spread">
                      {item.description || item.category || 'MERCADO'}
                      {item.provider ? ` • ${item.provider === 'BINANCE_USDM_FUTURES' ? 'BINANCE FUTURES' : 'MT5'}` : ''}
                    </span>
                  </div>
                  <button type="button" className="hk-action-sm-btn">
                    SELECIONAR 📊
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '10px', borderTop: '1px solid var(--hk-border-subdued)', fontSize: '11px', color: 'var(--hk-text-muted)' }}>
          <span>{filtered.length} ativo(s) disponível(is)</span>
          <button type="button" className="hk-pill-btn" onClick={onClose}>Fechar</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
