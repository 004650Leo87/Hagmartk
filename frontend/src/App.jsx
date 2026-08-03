import { useEffect, useState } from 'react';
import './App.css';
import { getSymbols } from './services/api';

const menuItems = [
  'Painel',
  'Mercado',
  'Estratégias',
  'Backtest',
  'IA Hagmartk',
  'Automação',
  'Telegram',
  'Configurações',
];

const fallbackMarkets = [
  {
    symbol: 'XAUUSD',
    price: '--',
    change: 'Aguardando',
    positive: true,
  },
  {
    symbol: 'BTCUSD',
    price: '--',
    change: 'Aguardando',
    positive: true,
  },
  {
    symbol: 'EURUSD',
    price: '--',
    change: 'Aguardando',
    positive: true,
  },
  {
    symbol: 'NAS100',
    price: '--',
    change: 'Aguardando',
    positive: true,
  },
];

function normalizeSymbols(data) {
  let rawSymbols = [];

  if (Array.isArray(data)) {
    rawSymbols = data;
  } else if (Array.isArray(data?.symbols)) {
    rawSymbols = data.symbols;
  }

  return rawSymbols
    .map((item) => {
      if (typeof item === 'string') {
        return item;
      }

      if (item && typeof item.name === 'string') {
        return item.name;
      }

      if (item && typeof item.symbol === 'string') {
        return item.symbol;
      }

      return null;
    })
    .filter(Boolean);
}

function App() {
  const [symbols, setSymbols] = useState([]);
  const [loadingSymbols, setLoadingSymbols] = useState(true);
  const [symbolsError, setSymbolsError] = useState('');

  useEffect(() => {
    let active = true;

    async function loadSymbols() {
      try {
        setLoadingSymbols(true);
        setSymbolsError('');

        const data = await getSymbols();
        const normalizedSymbols = normalizeSymbols(data);

        if (active) {
          setSymbols(normalizedSymbols);
        }
      } catch (error) {
        console.error('Erro ao carregar os ativos:', error);

        if (active) {
          setSymbolsError('Não foi possível carregar os ativos do MetaTrader.');
        }
      } finally {
        if (active) {
          setLoadingSymbols(false);
        }
      }
    }

    loadSymbols();

    return () => {
      active = false;
    };
  }, []);

  const markets =
    symbols.length > 0
      ? symbols.slice(0, 4).map((symbol) => ({
          symbol,
          price: '--',
          change: 'Conectado',
          positive: true,
        }))
      : fallbackMarkets;

  return (
    <div className="platform">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">H</span>

          <div>
            <strong>Hagmartk</strong>
            <small>Inteligência de Mercado</small>
          </div>
        </div>

        <nav className="menu">
          {menuItems.map((item, index) => (
            <button
              key={item}
              className={index === 0 ? 'menu-item active' : 'menu-item'}
              type="button"
            >
              {item}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="connection-dot" />
          Sistema operacional
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Visão geral</p>
            <h1>Painel</h1>
          </div>

          <div className="topbar-actions">
            <div className="connection-badge">
              <span className="connection-dot" />
              API conectada
            </div>

            <div className="profile">
              <span className="avatar">LS</span>

              <div>
                <strong>Leonardo Silva</strong>
                <small>Administrador</small>
              </div>
            </div>
          </div>
        </header>

        <main className="content">
          <section className="summary-grid">
            <article className="summary-card">
              <span>Saldo</span>
              <strong>US$ --</strong>
              <small>Aguardando dados da conta</small>
            </article>

            <article className="summary-card">
              <span>Patrimônio</span>
              <strong>US$ --</strong>
              <small>Aguardando atualização</small>
            </article>

            <article className="summary-card">
              <span>Margem livre</span>
              <strong>US$ --</strong>
              <small>Aguardando MetaTrader</small>
            </article>

            <article className="summary-card">
              <span>Lucro do dia</span>
              <strong className="positive">US$ --</strong>
              <small>Nenhuma posição identificada</small>
            </article>
          </section>

          <section className="main-grid">
            <article className="panel chart-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Mercado principal</p>
                  <h2>XAUUSD</h2>
                </div>

                <div className="market-price">
                  <strong>--</strong>
                  <span className="positive">Conectando</span>
                </div>
              </div>

              <div className="chart-placeholder">
                <div className="chart-line line-one" />
                <div className="chart-line line-two" />

                <div className="chart-message">
                  <strong>Gráfico em tempo real</strong>
                  <span>
                    A integração com os candles do MetaTrader será exibida
                    nesta área.
                  </span>
                </div>
              </div>
            </article>

            <article className="panel watchlist-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Monitoramento</p>
                  <h2>Lista de observação</h2>
                </div>

                <button className="ghost-button" type="button">
                  Ver todos
                </button>
              </div>

              {loadingSymbols && (
                <p className="api-message">Carregando ativos reais...</p>
              )}

              {!loadingSymbols && symbolsError && (
                <p className="api-message error-message">{symbolsError}</p>
              )}

              {!loadingSymbols &&
                !symbolsError &&
                symbols.length > 0 && (
                  <p className="api-message">
                    {symbols.length} ativos recebidos do MetaTrader.
                  </p>
                )}

              <div className="watchlist">
                {markets.map((market) => (
                  <div className="watchlist-row" key={market.symbol}>
                    <div>
                      <strong>{market.symbol}</strong>
                      <small>Disponível no MetaTrader</small>
                    </div>

                    <div className="watchlist-price">
                      <strong>{market.price}</strong>

                      <span
                        className={
                          market.positive ? 'positive' : 'negative'
                        }
                      >
                        {market.change}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </article>

            <article className="panel intelligence-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Inteligência artificial</p>
                  <h2>Leitura Hagmartk</h2>
                </div>

                <span className="analysis-status">Em análise</span>
              </div>

              <div className="signal">
                <div className="signal-icon">AI</div>

                <div>
                  <strong>Aguardando dados de mercado</strong>

                  <p>
                    A inteligência será ativada depois que os candles reais
                    forem conectados ao painel.
                  </p>
                </div>
              </div>

              <div className="confidence">
                <div>
                  <span>Confiança atual</span>
                  <strong>0%</strong>
                </div>

                <div className="confidence-track">
                  <span style={{ width: '0%' }} />
                </div>
              </div>
            </article>

            <article className="panel modules-panel">
              <div className="panel-header">
                <div>
                  <p className="eyebrow">Operações</p>
                  <h2>Módulos</h2>
                </div>
              </div>

              <div className="module-grid">
                <button type="button">Executar backtest</button>
                <button type="button">Abrir estratégias</button>
                <button type="button">Configurar Telegram</button>
                <button type="button">Central de automações</button>
              </div>
            </article>
          </section>
        </main>
      </section>
    </div>
  );
}

export default App;