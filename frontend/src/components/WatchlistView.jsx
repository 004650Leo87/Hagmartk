import React, { useEffect, useState } from 'react';
import { getMarketCatalog } from '../services/api';

export default function WatchlistView({
  watchlist = [],
  onSelectSymbol,
  onAddToWatchlist,
  onRemoveFromWatchlist,
}) {
  const [catalog, setCatalog] = useState([]);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('TODAS');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadCatalog() {
      try {
        const res = await getMarketCatalog();
        setCatalog(res || []);
      } catch (err) {
        console.error('Erro ao carregar catálogo:', err);
      } finally {
        setLoading(false);
      }
    }
    loadCatalog();
  }, []);

  const categories = ['TODAS', 'FOREX', 'METALS', 'CRYPTO', 'INDICES'];

  const filteredCatalog = catalog.filter((item) => {
    const matchesSearch =
      item.symbol.toLowerCase().includes(search.toLowerCase()) ||
      (item.description && item.description.toLowerCase().includes(search.toLowerCase()));
    const matchesCategory =
      categoryFilter === 'TODAS' || (item.category && item.category.toUpperCase() === categoryFilter);
    return matchesSearch && matchesCategory;
  });

  const isFav = (symbol) => watchlist.some((w) => w.symbol === symbol);

  return (
    <div className="hk-view-container">
      <div className="hk-view-header">
        <div>
          <h2 className="hk-view-title">CATÁLOGO DE ATIVOS & WATCHLIST</h2>
          <p className="hk-view-subtitle">Explore os ativos disponíveis no MetaTrader 5 e monte sua lista de acompanhamento.</p>
        </div>

        <div className="hk-search-bar">
          <input
            type="text"
            className="hk-input"
            placeholder="Buscar por símbolo ou descrição..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Categories Bar */}
      <div className="hk-pills-bar">
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`hk-pill-btn ${categoryFilter === cat ? 'active' : ''}`}
            onClick={() => setCategoryFilter(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Catalog Table */}
      <div className="hk-table-card">
        {loading ? (
          <div className="hk-loading">Carregando catálogo do MetaTrader 5...</div>
        ) : filteredCatalog.length === 0 ? (
          <div className="hk-empty">Nenhum ativo encontrado para os filtros selecionados.</div>
        ) : (
          <table className="hk-table">
            <thead>
              <tr>
                <th>FAV</th>
                <th>SÍMBOLO</th>
                <th>CATEGORIA</th>
                <th>DESCRIÇÃO</th>
                <th>BROKER PATH</th>
                <th>AÇÕES</th>
              </tr>
            </thead>
            <tbody>
              {filteredCatalog.map((item) => {
                const favorite = isFav(item.symbol);
                return (
                  <tr key={item.symbol}>
                    <td>
                      <button
                        type="button"
                        className={`hk-star-btn ${favorite ? 'fav' : ''}`}
                        onClick={() => {
                          if (favorite) onRemoveFromWatchlist(item.symbol);
                          else onAddToWatchlist(item.symbol);
                        }}
                      >
                        {favorite ? '★' : '☆'}
                      </button>
                    </td>
                    <td>
                      <strong className="hk-symbol-code">{item.symbol}</strong>
                    </td>
                    <td>
                      <span className="hk-badge-category">{item.category || 'FOREX'}</span>
                    </td>
                    <td>{item.description || item.name || '--'}</td>
                    <td className="hk-text-muted">{item.broker_path || item.path || '--'}</td>
                    <td>
                      <button
                        type="button"
                        className="hk-action-sm-btn"
                        onClick={() => onSelectSymbol(item.symbol)}
                      >
                        ABRIR GRÁFICO 📊
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
