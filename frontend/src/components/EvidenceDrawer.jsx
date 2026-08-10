import { useState } from 'react';

const PAGE_SIZE = 20;

const DIRECTION_MAP = {
  BEARISH: '🔻 Baixista',
  BULLISH: '🔺 Altista',
};

export default function EvidenceDrawer({ events = [], onActivateEvidence }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState('TODOS');

  const filtered = events.filter((evt) => {
    if (filter === 'TODOS') return true;
    if (filter === 'ALTISTA') return evt.direction === 'BULLISH';
    if (filter === 'BAIXISTA') return evt.direction === 'BEARISH';
    return true;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const pageEvents = filtered.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);

  function handleFilterChange(f) {
    setFilter(f);
    setPage(0);
  }

  return (
    <div className={`evidence-drawer-container ${open ? 'open' : 'closed'}`}>
      {/* Trigger button */}
      <button
        type="button"
        id="evidence-drawer-toggle"
        className={`evidence-drawer-toggle ${open ? 'active' : ''}`}
        onClick={() => setOpen((p) => !p)}
        title={open ? 'Fechar Evidências HDM' : 'Abrir Evidências HDM'}
      >
        ⚡ EVIDÊNCIAS{events.length > 0 ? ` (${events.length})` : ''}
        <span className="evidence-drawer-arrow">{open ? '▲' : '▼'}</span>
      </button>

      {/* Drawer panel */}
      {open && (
        <div className="evidence-drawer-panel" role="complementary" aria-label="Evidências históricas HDM">
          <div className="evidence-drawer-header">
            <div className="evidence-drawer-meta">
              <span className="evidence-drawer-badge">HISTÓRICO</span>
              <span className="evidence-drawer-label">Evidências de Pesquisa HDM</span>
              <span className="evidence-drawer-note">• Não são alertas Shadow prospectivos</span>
            </div>

            {/* Filters */}
            <div className="evidence-drawer-filters">
              {['TODOS', 'ALTISTA', 'BAIXISTA'].map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`evidence-filter-btn ${filter === f ? 'active' : ''}`}
                  onClick={() => handleFilterChange(f)}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* Event list */}
          <div className="evidence-drawer-list">
            {pageEvents.length === 0 ? (
              <div className="evidence-drawer-empty">
                Nenhuma evidência histórica encontrada.
              </div>
            ) : (
              pageEvents.map((evt, idx) => {
                const isBear = evt.direction === 'BEARISH';
                return (
                  <button
                    key={evt.event_id || idx}
                    type="button"
                    className={`evidence-item ${isBear ? 'bearish' : 'bullish'}`}
                    onClick={() => onActivateEvidence && onActivateEvidence(evt)}
                  >
                    <div className="evidence-item-header">
                      <span className="evidence-item-dir">{DIRECTION_MAP[evt.direction] || evt.direction}</span>
                      <span className="evidence-item-tf">{evt.timeframe}</span>
                      <span className="evidence-item-idx">#{currentPage * PAGE_SIZE + idx + 1}</span>
                    </div>
                    <div className="evidence-item-times">
                      <span>P1: {evt.metadata?.pivot_1_time?.slice(0, 16) || '--'}</span>
                      <span>P2: {evt.metadata?.pivot_2_time?.slice(0, 16) || evt.pivot_2_time?.slice(0, 16) || '--'}</span>
                    </div>
                    <span className="evidence-item-cta">Ativar Evidence Mode →</span>
                  </button>
                );
              })
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="evidence-drawer-pagination">
              <button
                type="button"
                className="evidence-page-btn"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={currentPage === 0}
              >
                ← Anterior
              </button>
              <span className="evidence-page-info">
                {currentPage + 1} / {totalPages}
              </span>
              <button
                type="button"
                className="evidence-page-btn"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={currentPage >= totalPages - 1}
              >
                Próxima →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
