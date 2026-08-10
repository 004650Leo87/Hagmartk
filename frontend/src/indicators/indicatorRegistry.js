/**
 * Registro e Metadados de Indicadores Visuais do Usuário.
 *
 * Define o catálogo extensível de indicadores (EMA, RSI).
 */

export const AVAILABLE_INDICATORS = [
  {
    id: 'ema',
    name: 'Média Móvel Exponencial (EMA)',
    shortName: 'EMA',
    type: 'OVERLAY',
    category: 'TENDÊNCIA',
    defaultPeriod: 20,
    presetPeriods: [9, 20, 50, 100, 200],
    defaultColor: '#ff9800',
    description: 'Média móvel ponderada com maior peso sobre os preços mais recentes.',
  },
  {
    id: 'rsi',
    name: 'Índice de Força Relativa (RSI)',
    shortName: 'RSI',
    type: 'PANE',
    category: 'MOMENTUM',
    defaultPeriod: 14,
    presetPeriods: [7, 14, 21, 28],
    defaultColor: '#29b6f6',
    description: 'Oscilador de momentum que mede a velocidade e a variação das mudanças de preço (0 a 100).',
  },
];

export const STORAGE_KEY = 'hagmartk_user_visual_indicators_v1';

export function loadSavedUserIndicators() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed;
    }
  } catch (e) {
    console.error('Erro ao ler indicadores do localStorage:', e);
  }
  return [];
}

export function saveUserIndicators(indicators) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(indicators));
  } catch (e) {
    console.error('Erro ao salvar indicadores no localStorage:', e);
  }
}
