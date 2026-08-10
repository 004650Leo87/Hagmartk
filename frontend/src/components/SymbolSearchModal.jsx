import { createPortal } from 'react-dom';
import { useEffect, useMemo, useRef, useState } from 'react';

const ASSET_CLASS_LABELS = {
  FOREX: 'Forex',
  METALS: 'Metais',
  CRYPTO: 'Cripto',
  INDICES: 'Índices',
  ENERGY: 'Energia',
  STOCKS: 'Ações',
  OTHER: 'Outros',
};

const ASSET_CLASS_ORDER = ['FOREX', 'METALS', 'CRYPTO', 'INDICES', 'ENERGY', 'STOCKS', 'OTHER'];

export default function SymbolSearchModal({ symbols = [], watchlist = [], onAdd, onClose }) {
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
    function onKey(e) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const filteredSymbols = useMemo(() => {
    const q = query.trim().toUpperCase();
    return symbols.filter((s) => {
      const name = (s.symbol || s.name || s).toUpperCase();
      const desc = (s.description || '').toUpperCase();
      return !q || name.includes(q) || desc.includes(q);
    });
  }, [symbols, query]);

  const grouped = useMemo(() => {
    const groups = {};
    for (const s of filteredSymbols) {
      const cat = s.category || s.asset_class || 'OTHER';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(s);
    }
    return groups;
  }, [filteredSymbols]);

  const watchlistSet = useMemo(() => new Set(watchlist.map((s) => s.symbol || s)), [watchlist]);

  return createPortal(
    <div
      className="symbol-search-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Buscar ativo"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="symbol-search-modal">
        <div className="symbol-search-header">
          <h3 className="symbol-search-title">Buscar Ativo</h3>
          <button type="button" className="symbol-search-close" onClick={onClose} aria-label="Fechar">×</button>
        </div>

        <div className="symbol-search-input-wrapper">
          <span className="symbol-search-icon">🔍</span>
          <input
            ref={inputRef}
            type="text"
            id="symbol-search-input"
            className="symbol-search-input"
            placeholder="Buscar ativo... (ex: EURUSD, XAUUSD, BTC)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          {query && (
            <button type="button" className="symbol-search-clear" onClick={() => setQuery('')}>×</button>
          )}
        </div>

        <div className="symbol-search-body">
          {filteredSymbols.length === 0 ? (
            <div className="symbol-search-empty">
              Nenhum ativo encontrado para "{query}".
            </div>
          ) : (
            ASSET_CLASS_ORDER.filter((cat) => grouped[cat]?.length > 0).map((cat) => (
              <div key={cat} className="symbol-group">
                <div className="symbol-group-label">{ASSET_CLASS_LABELS[cat] || cat}</div>
                <div className="symbol-group-list">
                  {grouped[cat].map((s) => {
                    const sym = s.symbol || s.name || s;
                    const inWatchlist = watchlistSet.has(sym);
                    return (
                      <button
                        key={sym}
                        type="button"
                        id={`symbol-item-${sym}`}
                        className={`symbol-item ${inWatchlist ? 'in-watchlist' : ''}`}
                        onClick={() => { if (!inWatchlist) { onAdd(sym); onClose(); } }}
                        disabled={inWatchlist}
                        title={inWatchlist ? 'Já na watchlist' : `Adicionar ${sym}`}
                      >
                        <span className="symbol-item-name">{sym}</span>
                        {s.description && (
                          <span className="symbol-item-desc">{s.description}</span>
                        )}
                        <span className={`symbol-item-action ${inWatchlist ? 'already' : 'add'}`}>
                          {inWatchlist ? '✓' : '+'}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="symbol-search-footer">
          <span>{filteredSymbols.length} ativo(s) encontrado(s)</span>
          <button type="button" className="symbol-search-cancel" onClick={onClose}>Fechar</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
