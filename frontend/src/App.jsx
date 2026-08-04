import { useEffect, useMemo, useState } from 'react';
import './App.css';
import MarketChart from './components/MarketChart';

import {
  getAccountPositions,
  getAccountSummary,
  getQuotes,
  getSymbols,
  getTodayHistory,
} from './services/api';
const menuItems = [
  { id: 'dashboard', label: 'Painel', icon: '▦' },
  { id: 'market', label: 'Mercado', icon: '⌁' },
  { id: 'strategies', label: 'Estratégias', icon: '◇' },
  { id: 'backtest', label: 'Backtest', icon: '↻' },
  { id: 'ai', label: 'IA Hagmartk', icon: 'IA' },
  { id: 'automation', label: 'Automação', icon: '⚡' },
  { id: 'telegram', label: 'Telegram', icon: '➤' },
  { id: 'settings', label: 'Configurações', icon: '⚙' },
];

const rightTabs = [
  { id: 'watchlist', label: 'Ativos' },
  { id: 'positions', label: 'Posições' },
  { id: 'alerts', label: 'Alertas' },
  { id: 'ai', label: 'IA' },
];

const dockTabs = [
  { id: 'positions', label: 'Posições' },
  { id: 'orders', label: 'Ordens' },
  { id: 'history', label: 'Histórico' },
  { id: 'logs', label: 'Registros' },
];

const timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'];

const fallbackMarkets = [
  {
    symbol: 'XAUUSD',
    bid: null,
    ask: null,
    spreadPoints: null,
    digits: 2,
    time: null,
    error: '',
  },
  {
    symbol: 'EURUSD',
    bid: null,
    ask: null,
    spreadPoints: null,
    digits: 5,
    time: null,
    error: '',
  },
  {
    symbol: 'GBPUSD',
    bid: null,
    ask: null,
    spreadPoints: null,
    digits: 5,
    time: null,
    error: '',
  },
  {
    symbol: 'USDJPY',
    bid: null,
    ask: null,
    spreadPoints: null,
    digits: 3,
    time: null,
    error: '',
  },
  {
    symbol: 'BTCUSD',
    bid: null,
    ask: null,
    spreadPoints: null,
    digits: 2,
    time: null,
    error: '',
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

function normalizeQuotes(data) {
  if (!Array.isArray(data)) {
    return [];
  }

  return data
    .map((item) => {
      if (!item || typeof item.symbol !== 'string') {
        return null;
      }

      const bid = Number(item.bid);
      const ask = Number(item.ask);
      const last = Number(item.last);
      const spread = Number(item.spread);
      const spreadPoints = Number(item.spread_points);
      const digits = Number(item.digits);

      return {
        symbol: item.symbol,
        bid: Number.isFinite(bid) ? bid : null,
        ask: Number.isFinite(ask) ? ask : null,
        last: Number.isFinite(last) ? last : null,
        spread: Number.isFinite(spread) ? spread : null,
        spreadPoints: Number.isFinite(spreadPoints)
          ? spreadPoints
          : null,
        digits: Number.isInteger(digits) ? digits : 2,
        time: item.time ?? null,
        error: item.error ?? '',
      };
    })
    .filter(Boolean);
}

function formatPrice(value, digits = 2) {
  const numericValue = Number(value);

  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(numericValue)
  ) {
    return '--';
  }

  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(numericValue);
}

function formatMoney(value, currency = 'USD') {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return `${currency} --`;
  }

  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: currency || 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numericValue);
}

function formatNumber(value, digits = 2) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return '--';
  }

  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(numericValue);
}

function formatTime(value) {
  if (!value) {
    return '--:--:--';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return '--:--:--';
  }

  return date.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatDateTime(value) {
  if (!value) {
    return '--';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return '--';
  }

  return date.toLocaleString('pt-BR');
}

function profitClass(value) {
  const number = Number(value);

  if (!Number.isFinite(number) || number === 0) {
    return '';
  }

  return number > 0 ? 'positive' : 'negative';
}

function App() {
  const [activeView, setActiveView] = useState('dashboard');

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [bottomDockOpen, setBottomDockOpen] = useState(true);
  const [focusMode, setFocusMode] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [activeRightTab, setActiveRightTab] = useState('watchlist');
  const [activeDockTab, setActiveDockTab] = useState('positions');

  const [selectedSymbol, setSelectedSymbol] = useState('XAUUSD');
  const [selectedTimeframe, setSelectedTimeframe] = useState('M5');

  const [symbols, setSymbols] = useState([]);
  const [loadingSymbols, setLoadingSymbols] = useState(true);
  const [symbolsError, setSymbolsError] = useState('');

  const [quotes, setQuotes] = useState([]);
  const [loadingQuotes, setLoadingQuotes] = useState(true);
  const [quotesError, setQuotesError] = useState('');

  const [account, setAccount] = useState(null);
  const [accountError, setAccountError] = useState('');
  const [loadingAccount, setLoadingAccount] = useState(true);

  const [positions, setPositions] = useState([]);
  const [positionsError, setPositionsError] = useState('');

  const [dailyHistory, setDailyHistory] = useState(null);
  const [historyError, setHistoryError] = useState('');

  const [lastUpdate, setLastUpdate] = useState(null);

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
          setSymbolsError(
            'Não foi possível carregar os ativos do MetaTrader.',
          );
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

  useEffect(() => {
    let active = true;
    let intervalId = null;
    let requestInProgress = false;

    async function loadQuotes() {
      if (requestInProgress) {
        return;
      }

      requestInProgress = true;

      try {
        setQuotesError('');

        const data = await getQuotes();
        const normalizedQuotes = normalizeQuotes(data);

        if (active) {
          setQuotes(normalizedQuotes);
          setLastUpdate(new Date());
        }
      } catch (error) {
        console.error('Erro ao carregar as cotações:', error);

        if (active) {
          setQuotesError(
            'Não foi possível atualizar as cotações do MetaTrader.',
          );
        }
      } finally {
        requestInProgress = false;

        if (active) {
          setLoadingQuotes(false);
        }
      }
    }

    loadQuotes();
    intervalId = window.setInterval(loadQuotes, 2000);

    return () => {
      active = false;

      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, []);

  useEffect(() => {
    let active = true;
    let intervalId = null;
    let requestInProgress = false;

    async function loadAccountData() {
      if (requestInProgress) {
        return;
      }

      requestInProgress = true;

      try {
        const results = await Promise.allSettled([
          getAccountSummary(),
          getAccountPositions(),
          getTodayHistory(),
        ]);

        if (!active) {
          return;
        }

        const [accountResult, positionsResult, historyResult] =
          results;

        if (accountResult.status === 'fulfilled') {
          setAccount(accountResult.value);
          setAccountError('');
        } else {
          console.error(
            'Erro ao carregar a conta:',
            accountResult.reason,
          );

          setAccountError(
            accountResult.reason?.message ||
              'Não foi possível carregar a conta.',
          );
        }

        if (positionsResult.status === 'fulfilled') {
          setPositions(
            Array.isArray(positionsResult.value)
              ? positionsResult.value
              : [],
          );

          setPositionsError('');
        } else {
          console.error(
            'Erro ao carregar posições:',
            positionsResult.reason,
          );

          setPositionsError(
            positionsResult.reason?.message ||
              'Não foi possível carregar as posições.',
          );
        }

        if (historyResult.status === 'fulfilled') {
          setDailyHistory(historyResult.value);
          setHistoryError('');
        } else {
          console.error(
            'Erro ao carregar histórico:',
            historyResult.reason,
          );

          setHistoryError(
            historyResult.reason?.message ||
              'Não foi possível carregar o histórico.',
          );
        }

        setLastUpdate(new Date());
      } finally {
        requestInProgress = false;

        if (active) {
          setLoadingAccount(false);
        }
      }
    }

    loadAccountData();

    intervalId = window.setInterval(loadAccountData, 3000);

    return () => {
      active = false;

      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, []);

  useEffect(() => {
    function handleFullscreenChange() {
      setIsFullscreen(Boolean(document.fullscreenElement));
    }

    document.addEventListener(
      'fullscreenchange',
      handleFullscreenChange,
    );

    return () => {
      document.removeEventListener(
        'fullscreenchange',
        handleFullscreenChange,
      );
    };
  }, []);

  const markets = useMemo(() => {
    return quotes.length > 0 ? quotes : fallbackMarkets;
  }, [quotes]);

  const selectedQuote = useMemo(() => {
    return (
      markets.find(
        (market) => market.symbol === selectedSymbol,
      ) ??
      markets[0] ??
      fallbackMarkets[0]
    );
  }, [markets, selectedSymbol]);

  const selectedPrice = useMemo(() => {
    if (
      selectedQuote.bid !== null &&
      selectedQuote.ask !== null
    ) {
      return (selectedQuote.bid + selectedQuote.ask) / 2;
    }

    return selectedQuote.bid ?? selectedQuote.ask;
  }, [selectedQuote]);

  const accountCurrency = account?.currency || 'USD';

  const accountConnected =
    Boolean(account?.connected) && !accountError;

  const apiConnected =
    !quotesError &&
    quotes.length > 0 &&
    accountConnected;

  const todayDeals = useMemo(() => {
    if (!Array.isArray(dailyHistory?.deals)) {
      return [];
    }

    return dailyHistory.deals;
  }, [dailyHistory]);

  const platformClasses = [
    'terminal-platform',
    sidebarCollapsed ? 'sidebar-is-collapsed' : '',
    rightPanelOpen
      ? 'right-panel-is-open'
      : 'right-panel-is-closed',
    bottomDockOpen ? 'dock-is-open' : 'dock-is-closed',
    focusMode ? 'focus-mode' : '',
  ]
    .filter(Boolean)
    .join(' ');

  async function toggleFullscreen() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen();
      } else {
        await document.exitFullscreen();
      }
    } catch (error) {
      console.error(
        'Não foi possível alterar o modo de tela cheia:',
        error,
      );
    }
  }

  return (
    <div className={platformClasses}>
      <aside className="terminal-sidebar">
        <div className="sidebar-brand">
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() =>
              setSidebarCollapsed((current) => !current)
            }
            title={
              sidebarCollapsed
                ? 'Expandir menu'
                : 'Recolher menu'
            }
          >
            {sidebarCollapsed ? '›' : '‹'}
          </button>

          <div className="brand-symbol">H</div>

          <div className="brand-copy">
            <strong>Hagmartk</strong>
            <span>Inteligência de mercado</span>
          </div>
        </div>

        <nav className="terminal-menu">
          {menuItems.map((item) => (
            <button
              key={item.id}
              type="button"
              className={
                activeView === item.id
                  ? 'terminal-menu-item active'
                  : 'terminal-menu-item'
              }
              onClick={() => setActiveView(item.id)}
              title={item.label}
            >
              <span className="menu-icon">{item.icon}</span>
              <span className="menu-label">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="system-monitor">
          <div className="system-monitor-header">
            <span className="status-light" />
            <strong>Sistema operacional</strong>
          </div>

          <div className="system-monitor-body">
            <div>
              <span>MetaTrader</span>

              <strong
                className={
                  accountConnected ? 'online' : 'offline'
                }
              >
                {accountConnected ? 'On-line' : 'Off-line'}
              </strong>
            </div>

            <div>
              <span>API</span>

              <strong
                className={
                  apiConnected ? 'online' : 'offline'
                }
              >
                {apiConnected ? 'Conectada' : 'Aguardando'}
              </strong>
            </div>

            <div>
              <span>Conta</span>
              <strong>{account?.login || '--'}</strong>
            </div>

            <div>
              <span>Servidor</span>
              <strong>{account?.server || '--'}</strong>
            </div>

            <div>
              <span>Alavancagem</span>

              <strong>
                {account?.leverage
                  ? `1:${account.leverage}`
                  : '--'}
              </strong>
            </div>

            <div>
              <span>Ativos</span>
              <strong>{symbols.length || '--'}</strong>
            </div>

            <div>
              <span>Atualização</span>
              <strong>3s</strong>
            </div>
          </div>
        </div>
      </aside>

      <section className="terminal-workspace">
        <header className="terminal-topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="mobile-menu-button"
              onClick={() =>
                setSidebarCollapsed((current) => !current)
              }
              title="Alternar menu"
            >
              ☰
            </button>

            <div className="instrument-selector">
              <span className="instrument-status" />

              <div>
                <strong>{selectedSymbol}</strong>
                <small>Mercado conectado</small>
              </div>
            </div>

            <div className="timeframe-selector">
              {timeframes.map((timeframe) => (
                <button
                  key={timeframe}
                  type="button"
                  className={
                    selectedTimeframe === timeframe
                      ? 'timeframe-button active'
                      : 'timeframe-button'
                  }
                  onClick={() =>
                    setSelectedTimeframe(timeframe)
                  }
                >
                  {timeframe}
                </button>
              ))}
            </div>
          </div>

          <div className="topbar-right">
            <div
              className={
                accountConnected
                  ? 'connection-pill connected'
                  : 'connection-pill disconnected'
              }
            >
              <span className="status-light" />

              {accountConnected
                ? 'MetaTrader conectado'
                : 'MetaTrader desconectado'}
            </div>

            <button
              type="button"
              className={
                focusMode
                  ? 'icon-action active'
                  : 'icon-action'
              }
              onClick={() =>
                setFocusMode((current) => !current)
              }
              title="Modo gráfico"
            >
              ◫
            </button>

            <button
              type="button"
              className="icon-action"
              onClick={() =>
                setRightPanelOpen((current) => !current)
              }
              title="Alternar painel lateral"
            >
              {rightPanelOpen ? '▮›' : '‹▮'}
            </button>

            <button
              type="button"
              className={
                isFullscreen
                  ? 'icon-action active'
                  : 'icon-action'
              }
              onClick={toggleFullscreen}
              title="Tela cheia"
            >
              {isFullscreen ? '↙' : '⛶'}
            </button>

            <div className="user-profile">
              <span className="user-avatar">LS</span>

              <div>
                <strong>Leonardo Silva</strong>
                <small>Administrador</small>
              </div>
            </div>
          </div>
        </header>

        <div className="market-command-bar">
          <div className="market-command-main">
            <span className="market-symbol">
              {selectedQuote.symbol}
            </span>

            <strong className="market-main-price">
              {formatPrice(
                selectedPrice,
                selectedQuote.digits ?? 2,
              )}
            </strong>

            <span className="market-detail">
              Compra{' '}
              <strong>
                {formatPrice(
                  selectedQuote.bid,
                  selectedQuote.digits ?? 2,
                )}
              </strong>
            </span>

            <span className="market-detail">
              Venda{' '}
              <strong>
                {formatPrice(
                  selectedQuote.ask,
                  selectedQuote.digits ?? 2,
                )}
              </strong>
            </span>

            <span className="market-detail">
              Spread{' '}
              <strong>
                {selectedQuote.spreadPoints ?? '--'} pontos
              </strong>
            </span>

            <span className="market-detail">
              Saldo{' '}
              <strong>
                {formatMoney(
                  account?.balance,
                  accountCurrency,
                )}
              </strong>
            </span>

            <span className="market-detail">
              Patrimônio{' '}
              <strong>
                {formatMoney(
                  account?.equity,
                  accountCurrency,
                )}
              </strong>
            </span>

            <span className="market-detail">
              Margem livre{' '}
              <strong>
                {formatMoney(
                  account?.margin_free,
                  accountCurrency,
                )}
              </strong>
            </span>

            <span className="market-detail">
              Resultado{' '}
              <strong
                className={profitClass(account?.profit)}
              >
                {formatMoney(
                  account?.profit,
                  accountCurrency,
                )}
              </strong>
            </span>
          </div>

          <div className="market-command-actions">
            <button type="button">Indicadores</button>
            <button type="button">Alertas</button>
            <button type="button">Estratégia</button>
            <button type="button">Layout</button>
          </div>
        </div>

        <main className="terminal-main">
          <section className="chart-workspace">
            <div className="chart-toolbar">
              <div className="drawing-tools">
                <button type="button" title="Cursor">
                  ↖
                </button>

                <button type="button" title="Linha">
                  ╱
                </button>

                <button type="button" title="Linha horizontal">
                  —
                </button>

                <button type="button" title="Retângulo">
                  □
                </button>

                <button type="button" title="Texto">
                  T
                </button>

                <button type="button" title="Medição">
                  ↔
                </button>
              </div>

              <div className="chart-toolbar-status">
                <span>Dados reais do MetaTrader</span>
                <strong>{selectedTimeframe}</strong>
              </div>
            </div>

            <div className="chart-stage">
              <MarketChart
                symbol={selectedSymbol}
                timeframe={selectedTimeframe}
                refreshInterval={2000}
              />
            </div>
          </section>

          <aside className="right-drawer">
            <div className="right-drawer-header">
              <div className="right-tabs">
                {rightTabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={
                      activeRightTab === tab.id
                        ? 'right-tab active'
                        : 'right-tab'
                    }
                    onClick={() => setActiveRightTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <button
                type="button"
                className="drawer-close"
                onClick={() => setRightPanelOpen(false)}
                title="Fechar painel"
              >
                ×
              </button>
            </div>

            <div className="right-drawer-content">
              {activeRightTab === 'watchlist' && (
                <>
                  <div className="watchlist-toolbar">
                    <div>
                      <strong>Lista de observação</strong>

                      <span>
                        {symbols.length || '--'} ativos disponíveis
                      </span>
                    </div>

                    <button type="button" title="Adicionar ativo">
                      +
                    </button>
                  </div>

                  {loadingSymbols && (
                    <p className="drawer-message">
                      Carregando ativos...
                    </p>
                  )}

                  {!loadingSymbols && symbolsError && (
                    <p className="drawer-message error">
                      {symbolsError}
                    </p>
                  )}

                  {loadingQuotes && (
                    <p className="drawer-message">
                      Carregando cotações...
                    </p>
                  )}

                  {!loadingQuotes && quotesError && (
                    <p className="drawer-message error">
                      {quotesError}
                    </p>
                  )}

                  <div className="terminal-watchlist">
                    {markets.map((market) => (
                      <button
                        key={market.symbol}
                        type="button"
                        className={
                          market.symbol === selectedSymbol
                            ? 'terminal-watchlist-row selected'
                            : 'terminal-watchlist-row'
                        }
                        onClick={() =>
                          setSelectedSymbol(market.symbol)
                        }
                      >
                        <div className="watchlist-symbol">
                          <strong>{market.symbol}</strong>

                          <span>
                            {market.error
                              ? 'Indisponível'
                              : formatTime(market.time)}
                          </span>
                        </div>

                        <div className="watchlist-values">
                          <strong>
                            {formatPrice(
                              market.bid,
                              market.digits ?? 2,
                            )}
                          </strong>

                          <span>
                            Venda{' '}
                            {formatPrice(
                              market.ask,
                              market.digits ?? 2,
                            )}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </>
              )}

              {activeRightTab === 'positions' && (
                <>
                  <div className="watchlist-toolbar">
                    <div>
                      <strong>Posições abertas</strong>

                      <span>
                        {positions.length} posição(ões)
                      </span>
                    </div>
                  </div>

                  {positionsError && (
                    <p className="drawer-message error">
                      {positionsError}
                    </p>
                  )}

                  {!positionsError &&
                    positions.length === 0 && (
                      <div className="empty-module">
                        <span>POS</span>
                        <strong>Nenhuma posição aberta</strong>

                        <p>
                          As operações abertas no MetaTrader
                          aparecerão automaticamente aqui.
                        </p>
                      </div>
                    )}

                  {positions.length > 0 && (
                    <div className="terminal-watchlist">
                      {positions.map((position) => (
                        <button
                          key={position.ticket}
                          type="button"
                          className="terminal-watchlist-row"
                          onClick={() =>
                            setSelectedSymbol(position.symbol)
                          }
                        >
                          <div className="watchlist-symbol">
                            <strong>
                              {position.symbol}{' '}
                              {position.type}
                            </strong>

                            <span>
                              Volume:{' '}
                              {formatNumber(
                                position.volume,
                                2,
                              )}
                            </span>
                          </div>

                          <div className="watchlist-values">
                            <strong
                              className={profitClass(
                                position.profit,
                              )}
                            >
                              {formatMoney(
                                position.profit,
                                accountCurrency,
                              )}
                            </strong>

                            <span>
                              Entrada{' '}
                              {formatPrice(
                                position.price_open,
                                2,
                              )}
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}

              {activeRightTab === 'alerts' && (
                <div className="empty-module">
                  <span>ALT</span>
                  <strong>Central de alertas</strong>

                  <p>
                    Alertas de preço, indicadores, liquidez e
                    estratégias aparecerão aqui.
                  </p>
                </div>
              )}

              {activeRightTab === 'ai' && (
                <div className="ai-drawer-module">
                  <div className="ai-module-heading">
                    <span>IA</span>

                    <div>
                      <strong>IA Hagmartk</strong>
                      <small>Motor em preparação</small>
                    </div>
                  </div>

                  <div className="ai-insight-card">
                    <span>Leitura atual</span>

                    <strong>
                      Mercado e conta conectados ao MetaTrader.
                    </strong>

                    <p>
                      A análise estrutural será ativada após a
                      integração dos candles.
                    </p>
                  </div>

                  <div className="ai-confidence">
                    <div>
                      <span>Integração do terminal</span>
                      <strong>65%</strong>
                    </div>

                    <div className="ai-confidence-track">
                      <span style={{ width: '65%' }} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </aside>
        </main>

        <section className="terminal-dock">
          <div className="dock-header">
            <div className="dock-tabs">
              {dockTabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={
                    activeDockTab === tab.id
                      ? 'dock-tab active'
                      : 'dock-tab'
                  }
                  onClick={() => {
                    setActiveDockTab(tab.id);
                    setBottomDockOpen(true);
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="dock-actions">
              <span>
                Atualização:{' '}
                <strong>
                  {lastUpdate
                    ? lastUpdate.toLocaleTimeString('pt-BR')
                    : '--:--:--'}
                </strong>
              </span>

              <button
                type="button"
                onClick={() =>
                  setBottomDockOpen((current) => !current)
                }
                title="Alternar painel inferior"
              >
                {bottomDockOpen ? '⌄' : '⌃'}
              </button>
            </div>
          </div>

          <div className="dock-content">
            {activeDockTab === 'positions' && (
              <div className="dock-table">
                <div className="dock-table-header">
                  <span>Ativo</span>
                  <span>Tipo</span>
                  <span>Volume</span>
                  <span>Entrada</span>
                  <span>Preço atual</span>
                  <span>Stop</span>
                  <span>Alvo</span>
                  <span>Resultado</span>
                </div>

                {loadingAccount && (
                  <div className="dock-empty-row">
                    Carregando dados da conta...
                  </div>
                )}

                {!loadingAccount &&
                  positions.length === 0 &&
                  !positionsError && (
                    <div className="dock-empty-row">
                      Nenhuma posição aberta.
                    </div>
                  )}

                {positionsError && (
                  <div className="dock-empty-row">
                    {positionsError}
                  </div>
                )}

                {positions.map((position) => (
                  <div
                    className="dock-table-header"
                    key={position.ticket}
                  >
                    <span>{position.symbol}</span>
                    <span>{position.type}</span>

                    <span>
                      {formatNumber(position.volume, 2)}
                    </span>

                    <span>
                      {formatPrice(position.price_open, 2)}
                    </span>

                    <span>
                      {formatPrice(
                        position.price_current,
                        2,
                      )}
                    </span>

                    <span>
                      {position.stop_loss
                        ? formatPrice(
                            position.stop_loss,
                            2,
                          )
                        : '--'}
                    </span>

                    <span>
                      {position.take_profit
                        ? formatPrice(
                            position.take_profit,
                            2,
                          )
                        : '--'}
                    </span>

                    <span
                      className={profitClass(
                        position.profit,
                      )}
                    >
                      {formatMoney(
                        position.profit,
                        accountCurrency,
                      )}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {activeDockTab === 'orders' && (
              <div className="dock-empty-state">
                A conexão das ordens pendentes será realizada
                depois das posições abertas.
              </div>
            )}

            {activeDockTab === 'history' && (
              <div className="dock-table">
                <div className="dock-table-header">
                  <span>Ativo</span>
                  <span>Tipo</span>
                  <span>Volume</span>
                  <span>Entrada</span>
                  <span>Data</span>
                  <span>Comissão</span>
                  <span>Swap</span>
                  <span>Resultado</span>
                </div>

                {historyError && (
                  <div className="dock-empty-row">
                    {historyError}
                  </div>
                )}

                {!historyError &&
                  todayDeals.length === 0 && (
                    <div className="dock-empty-row">
                      Nenhuma negociação registrada hoje.
                    </div>
                  )}

                {todayDeals.map((deal) => (
                  <div
                    className="dock-table-header"
                    key={deal.ticket}
                  >
                    <span>{deal.symbol || '--'}</span>
                    <span>{deal.type}</span>

                    <span>
                      {formatNumber(deal.volume, 2)}
                    </span>

                    <span>
                      {formatPrice(deal.price, 2)}
                    </span>

                    <span>{formatDateTime(deal.time)}</span>

                    <span>
                      {formatMoney(
                        deal.commission,
                        accountCurrency,
                      )}
                    </span>

                    <span>
                      {formatMoney(
                        deal.swap,
                        accountCurrency,
                      )}
                    </span>

                    <span
                      className={profitClass(
                        deal.net_profit,
                      )}
                    >
                      {formatMoney(
                        deal.net_profit,
                        accountCurrency,
                      )}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {activeDockTab === 'logs' && (
              <div className="dock-log">
                <span>
                  [Sistema] Interface Hagmartk iniciada.
                </span>

                <span>
                  [Mercado] Cotações recebidas do MetaTrader.
                </span>

                <span>
                  [Conta] Saldo:{' '}
                  {formatMoney(
                    account?.balance,
                    accountCurrency,
                  )}
                </span>

                <span>
                  [Conta] Patrimônio:{' '}
                  {formatMoney(
                    account?.equity,
                    accountCurrency,
                  )}
                </span>

                <span>
                  [Posições] {positions.length} posição(ões)
                  aberta(s).
                </span>

                <span>
                  [Histórico] {dailyHistory?.deals_count || 0}{' '}
                  negócio(s) registrado(s) hoje.
                </span>

                {accountError && (
                  <span>[Erro] {accountError}</span>
                )}
              </div>
            )}
          </div>
        </section>

        <footer className="terminal-statusbar">
          <div>
            <span className="status-light" />
            Sistema operacional
          </div>

          <div>
            <span>API</span>
            <strong>
              {apiConnected ? 'On-line' : 'Off-line'}
            </strong>
          </div>

          <div>
            <span>Conta</span>
            <strong>{account?.login || '--'}</strong>
          </div>

          <div>
            <span>Saldo</span>

            <strong>
              {formatMoney(
                account?.balance,
                accountCurrency,
              )}
            </strong>
          </div>

          <div>
            <span>Patrimônio</span>

            <strong>
              {formatMoney(
                account?.equity,
                accountCurrency,
              )}
            </strong>
          </div>

          <div>
            <span>Ativo</span>
            <strong>{selectedSymbol}</strong>
          </div>

          <div>
            <span>Período</span>
            <strong>{selectedTimeframe}</strong>
          </div>

          <div>
            <span>Corretora</span>
            <strong>{account?.company || '--'}</strong>
          </div>
        </footer>
      </section>
    </div>
  );
}

export default App;