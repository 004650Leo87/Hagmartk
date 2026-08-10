import { createPortal } from 'react-dom';
import { useEffect, useState } from 'react';
import { AVAILABLE_INDICATORS } from '../indicators/indicatorRegistry';

export default function IndicatorManagerModal({ activeIndicators = [], onAdd, onRemove, onToggleVisibility, onClose }) {
  const [selectedType, setSelectedType] = useState('ema');
  const [periodInput, setPeriodInput] = useState('20');
  const [customColor, setCustomColor] = useState('#ff9800');
  const [searchQuery, setSearchQuery] = useState('');

  const currentMeta = AVAILABLE_INDICATORS.find((i) => i.id === selectedType) || AVAILABLE_INDICATORS[0];

  useEffect(() => {
    if (currentMeta) {
      setPeriodInput(String(currentMeta.defaultPeriod));
      setCustomColor(currentMeta.defaultColor);
    }
  }, [selectedType, currentMeta]);

  function handleAdd() {
    const period = parseInt(periodInput, 10);
    if (isNaN(period) || period <= 0 || period > 500) {
      alert('Por favor, informe um período válido entre 1 e 500.');
      return;
    }

    const instanceId = `${selectedType}_${period}_${Date.now()}`;
    onAdd({
      instanceId,
      type: selectedType,
      period,
      color: customColor,
      visible: true,
    });
  }

  const filteredCatalog = AVAILABLE_INDICATORS.filter((ind) => {
    const q = searchQuery.trim().toLowerCase();
    return !q || ind.name.toLowerCase().includes(q) || ind.shortName.toLowerCase().includes(q) || ind.category.toLowerCase().includes(q);
  });

  return createPortal(
    <div
      className="symbol-search-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Gerenciador de Indicadores"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="symbol-search-modal" style={{ maxWidth: '560px' }}>
        <div className="symbol-search-header">
          <h3 className="symbol-search-title">📊 Gerenciador de Indicadores</h3>
          <button type="button" className="symbol-search-close" onClick={onClose} aria-label="Fechar">×</button>
        </div>

        <div className="symbol-search-input-wrapper">
          <span className="symbol-search-icon">🔍</span>
          <input
            type="text"
            className="symbol-search-input"
            placeholder="Buscar indicador... (ex: EMA, RSI)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button type="button" className="symbol-search-clear" onClick={() => setSearchQuery('')}>×</button>
          )}
        </div>

        <div className="symbol-search-body" style={{ maxHeight: '380px', overflowY: 'auto' }}>
          {/* Seção Adicionar Novo Indicador */}
          <div className="indicator-add-box">
            <span className="indicator-box-title">Adicionar Novo Indicador</span>

            <div className="indicator-grid">
              {filteredCatalog.map((ind) => (
                <button
                  key={ind.id}
                  type="button"
                  onClick={() => setSelectedType(ind.id)}
                  className={`indicator-type-card ${selectedType === ind.id ? 'selected' : ''}`}
                >
                  <div style={{ fontSize: '12px', fontWeight: '700' }}>{ind.name}</div>
                  <div style={{ fontSize: '10px', color: '#64748b' }}>{ind.category} • {ind.type === 'OVERLAY' ? 'Sobreposição' : 'Sub-Painel'}</div>
                </button>
              ))}
            </div>

            <div className="indicator-inputs-row">
              <div style={{ flex: 1 }}>
                <label className="indicator-field-label">Período:</label>
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={periodInput}
                  onChange={(e) => setPeriodInput(e.target.value)}
                  className="indicator-number-input"
                />
              </div>

              <div>
                <label className="indicator-field-label">Cor:</label>
                <input
                  type="color"
                  value={customColor}
                  onChange={(e) => setCustomColor(e.target.value)}
                  className="indicator-color-picker"
                />
              </div>

              <div>
                <button
                  type="button"
                  onClick={handleAdd}
                  className="indicator-add-btn"
                >
                  + Adicionar
                </button>
              </div>
            </div>

            {/* Presets Rápidos */}
            {currentMeta?.presetPeriods && (
              <div className="indicator-presets-row">
                <span className="indicator-field-label">Atalhos:</span>
                {currentMeta.presetPeriods.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPeriodInput(String(p))}
                    className="indicator-preset-btn"
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Seção Indicadores Ativos */}
          <div className="active-indicators-section">
            <span className="indicator-box-title">Indicadores Ativos ({activeIndicators.length})</span>

            {activeIndicators.length === 0 ? (
              <div className="drawer-message info">
                Nenhum indicador ativo no gráfico. Selecione um indicador acima e clique em + Adicionar.
              </div>
            ) : (
              <div>
                {activeIndicators.map((ind) => (
                  <div
                    key={ind.instanceId}
                    className="indicator-active-card"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: ind.color, display: 'inline-block' }} />
                      <strong style={{ color: '#f8fafc' }}>{ind.type.toUpperCase()} {ind.period}</strong>
                      <span style={{ fontSize: '10px', color: '#64748b' }}>({ind.type === 'ema' ? 'Preço' : 'Sub-painel'})</span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <button
                        type="button"
                        onClick={() => onToggleVisibility(ind.instanceId)}
                        className="indicator-preset-btn"
                        title={ind.visible ? 'Ocultar' : 'Exibir'}
                      >
                        {ind.visible ? '👁 Visível' : '🙈 Oculto'}
                      </button>

                      <button
                        type="button"
                        onClick={() => onRemove(ind.instanceId)}
                        style={{ background: '#7f1d1d', color: '#fca5a5', border: 'none', padding: '2px 8px', borderRadius: '4px', fontSize: '11px', cursor: 'pointer' }}
                        title="Remover indicador"
                      >
                        ✕ Remover
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="symbol-search-footer">
          <span>{activeIndicators.length} indicador(es) ativo(s)</span>
          <button type="button" className="symbol-search-cancel" onClick={onClose}>Fechar</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
