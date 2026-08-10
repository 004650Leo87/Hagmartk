import { createPortal } from 'react-dom';
import { useEffect, useMemo, useRef, useState } from 'react';
import './App.css';
import MarketChart from './components/MarketChart';
import ShadowStrategiesView from './components/ShadowStrategiesView';
import MarketAlertsSection from './components/MarketAlertsSection';
import { timeframeCodes } from './chart/chartConstants';
import HdfToastStack, { TOAST_STATES_WITH_NOTIFICATION } from './components/HdfToastStack';
import SymbolSearchModal from './components/SymbolSearchModal';
import EvidenceDrawer from './components/EvidenceDrawer';
import IndicatorManagerModal from './components/IndicatorManagerModal';
import { loadSavedUserIndicators, saveUserIndicators } from './indicators/indicatorRegistry';

import {
  getAccountPositions,
  getAccountSummary,
  getQuotes,
  getSymbols,
  getSystemHealth,
  getTimeframes,
  getTodayHistory,
  getShadowRecentEvents,
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
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
  const initialSelectedSymbolRef = useRef(selectedSymbol);
  const initialSelectedTimeframeRef = useRef(selectedTimeframe);

  const DEFAULT_FAVORITES = ['M1', 'M5', 'M15', 'H1', 'H4', 'D1'];
  const FAVORITES_STORAGE_KEY = 'hagmartk.favoriteTimeframes';

  const [favoriteTimeframes, setFavoriteTimeframes] = useState(() => {
    try {
      const stored = localStorage.getItem(FAVORITES_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch {
      // ignore
    }
    return DEFAULT_FAVORITES;
  });

  const [timeframeDrawerOpen, setTimeframeDrawerOpen] = useState(false);
  const timeframeToggleRef = useRef(null);
  const timeframePopupRef = useRef(null);
  const [drawerPopupPos, setDrawerPopupPos] = useState({ top: 0, left: 0 });

  const [showRSI, setShowRSI] = useState(false);
  const [showEMA50, setShowEMA50] = useState(false);
  const [showEMA200, setShowEMA200] = useState(false);
  const [showDivergences, setShowDivergences] = useState(false);

  // Indicator Manager (Fase 3C)
  const [userIndicators, setUserIndicators] = useState(() => loadSavedUserIndicators());
  const [indicatorManagerOpen, setIndicatorManagerOpen] = useState(false);

  function handleAddUserIndicator(newInd) {
    setUserIndicators((prev) => {
      const next = [...prev, newInd];
      saveUserIndicators(next);
      return next;
    });
  }

  function handleRemoveUserIndicator(instanceId) {
    setUserIndicators((prev) => {
      const next = prev.filter((i) => i.instanceId !== instanceId);
      saveUserIndicators(next);
      return next;
    });
  }

  function handleToggleUserIndicatorVisibility(instanceId) {
    setUserIndicators((prev) => {
      const next = prev.map((i) => (i.instanceId === instanceId ? { ...i, visible: !i.visible } : i));
      saveUserIndicators(next);
      return next;
    });
  }

  // Evidence Mode
  const [activeEvidenceEventId, setActiveEvidenceEventId] = useState(null);
  const [activeEvidenceData, setActiveEvidenceData] = useState(null);

  // HDF Toast
  const [toasts, setToasts] = useState([]);
  const seenToastIdsRef = useRef(new Set());

  // Watchlist dinâmica
  const [watchlistSymbols, setWatchlistSymbols] = useState([]);
  const [watchlistQuotes, setWatchlistQuotes] = useState([]);
  const [loadingWatchlist, setLoadingWatchlist] = useState(true);
  const [symbolSearchOpen, setSymbolSearchOpen] = useState(false);
  const [watchlistSearch, setWatchlistSearch] = useState('');
  
  // Para EvidenceDrawer (Mock se não houver dados, ou pode vir de outro lugar)
  const [divergenceEvents, setDivergenceEvents] = useState([]);

  const [symbols, setSymbols] = useState([]);
  const [loadingSymbols, setLoadingSymbols] = useState(true);
  const [symbolsError, setSymbolsError] = useState('');

  const [timeframes, setTimeframes] = useState([]);
  const [timeframeMap, setTimeframeMap] = useState({});

  const [systemHealth, setSystemHealth] = useState(null);
  const [systemHealthError, setSystemHealthError] = useState('');
  const [systemMonitorOpen, setSystemMonitorOpen] = useState(false);

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

          if (
            normalizedSymbols.length > 0 &&
            !normalizedSymbols.includes(initialSelectedSymbolRef.current)
          ) {
            setSelectedSymbol(normalizedSymbols[0]);
          }
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

    async function loadTimeframes() {
      try {
        const data = await getTimeframes();
        const normalized = Array.isArray(data)
          ? data
          : Array.isArray(data?.timeframes)
          ? data.timeframes
          : [];

        if (!active) {
          return;
        }

        setTimeframes(normalized);

        const map = normalized.reduce((acc, item) => {
          if (item && item.name && item.code != null) {
            acc[item.name] = item.code;
          }

          return acc;
        }, {});

        setTimeframeMap(map);

        if (
          normalized.length > 0 &&
          !normalized.some(
            (item) => item.name === initialSelectedTimeframeRef.current,
          )
        ) {
          setSelectedTimeframe(normalized[0].name);
        }
      } catch (error) {
        console.error('Erro ao carregar timeframes:', error);
      } finally {
        // loadingTimeframes state is not used in this scope.
      }
    }

    loadTimeframes();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let intervalId = null;

    async function loadSystemHealth() {
      try {
        setSystemHealthError('');

        const data = await getSystemHealth();

        if (!active) {
          return;
        }

        setSystemHealth(data);
      } catch (error) {
        console.error('Erro ao carregar o estado do sistema:', error);

        if (active) {
          setSystemHealth(null);
          setSystemHealthError(
            'Não foi possível carregar o status do sistema.',
          );
        }
      } finally {
        // loadingSystemHealth state is not used in this scope.
      }
    }

    loadSystemHealth();
    intervalId = window.setInterval(loadSystemHealth, 5000);

    return () => {
      active = false;

      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, []);

  // Efeito de carregamento e atualização periódica da Watchlist (Fase 3D)
  useEffect(() => {
    let active = true;
    let intervalId = null;

    async function loadWatchlistData() {
      try {
        const data = await getWatchlist();
        const quotes = Array.isArray(data) ? data : [];
        if (active) {
          setWatchlistQuotes(quotes);
          setWatchlistSymbols(quotes.map((q) => q.symbol || q.name || q));
          setLoadingWatchlist(false);
        }
      } catch (err) {
        console.error('Erro ao carregar a watchlist:', err);
        if (active) {
          setLoadingWatchlist(false);
        }
      }
    }

    loadWatchlistData();
    intervalId = window.setInterval(loadWatchlistData, 3000);

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

  useEffect(() => {
    try {
      localStorage.setItem(
        FAVORITES_STORAGE_KEY,
        JSON.stringify(favoriteTimeframes),
      );
    } catch {
      // ignore
    }
  }, [favoriteTimeframes]);

  useEffect(() => {
    if (!timeframeDrawerOpen) return undefined;

    function handleClickOutside(e) {
      const clickedToggle = timeframeToggleRef.current?.contains(e.target);
      const clickedPopup = timeframePopupRef.current?.contains(e.target);
      if (!clickedToggle && !clickedPopup) {
        setTimeframeDrawerOpen(false);
      }
    }

    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        setTimeframeDrawerOpen(false);
      }
    }

    function handleCloseOnResize() {
      setTimeframeDrawerOpen(false);
    }

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', handleCloseOnResize);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('resize', handleCloseOnResize);
    };
  }, [timeframeDrawerOpen]);

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

  const marketAdapterConnected =
    !systemHealthError &&
    Boolean(systemHealth?.adapter_connected);

  const apiConnected =
    !systemHealthError &&
    systemHealth !== null;

  const timeframeOptions =
    timeframes.length > 0
      ? timeframes
      : Object.keys(timeframeCodes).map((name) => ({
          name,
          code: timeframeCodes[name],
        }));

  const brokerName =
    systemHealth?.broker_name || account?.company || '--';

  const symbolsAvailable =
    typeof systemHealth?.symbol_count === 'number'
      ? systemHealth.symbol_count
      : symbols.length || '--';

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

  function handleNavigateToEvent(event) {
    if (event.symbol) setSelectedSymbol(event.symbol);
    if (event.timeframe) setSelectedTimeframe(event.timeframe);
    setActiveEvidenceEventId(event.event_id || event.alert_id);
    setActiveEvidenceData(event);
    setActiveView('market');
  }

  function handleDismissToast(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  async function handleAddToWatchlist(symbol) {
    try {
      await addToWatchlist(symbol);
      // Recarrega watchlist
      const data = await getWatchlist();
      const quotes = Array.isArray(data) ? data : [];
      setWatchlistQuotes(quotes);
      setWatchlistSymbols(quotes.map((q) => q.symbol || q.name || q));
    } catch (err) {
      console.error('Erro ao adicionar à watchlist:', err);
    }
  }

  async function handleRemoveFromWatchlist(symbol) {
    try {
      await removeFromWatchlist(symbol);
      const data = await getWatchlist();
      const quotes = Array.isArray(data) ? data : [];
      setWatchlistQuotes(quotes);
      setWatchlistSymbols(quotes.map((q) => q.symbol || q.name || q));
    } catch (err) {
      console.error('Erro ao remover da watchlist:', err);
    }
  }

  function handleActivateEvidence(evt) {
    setActiveEvidenceEventId(evt.event_id || null);
    setActiveEvidenceData(evt);
    if (evt.symbol) setSelectedSymbol(evt.symbol);
    if (evt.timeframe) setSelectedTimeframe(evt.timeframe);
    setActiveView('market');
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
          <div
            className={`system-monitor-header ${!systemMonitorOpen ? 'is-closed' : ''}`}
            onClick={() => setSystemMonitorOpen((prev) => !prev)}
            style={{ cursor: 'pointer', userSelect: 'none' }}
          >
            <span className={`status-light ${marketAdapterConnected ? 'online' : 'offline'}`} />
            <strong>Sistema operacional</strong>
            <span className="system-monitor-toggle" style={{ marginLeft: 'auto', fontSize: '10px', opacity: 0.7 }}>
              {systemMonitorOpen ? '▲' : '▼'}
            </span>
          </div>

          {systemMonitorOpen && (
            <div className="system-monitor-body">
              <div>
                <span>Adaptador MT5</span>

                <strong
                  className={
                    marketAdapterConnected ? 'online' : 'offline'
                  }
                >
                  {marketAdapterConnected ? 'On-line' : 'Off-line'}
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

              {account?.leverage ? (
                <div>
                  <span>Alavancagem</span>
                  <strong>1:{account.leverage}</strong>
                </div>
              ) : null}

              <div>
                <span>Ativos</span>
                <strong>{symbolsAvailable}</strong>
              </div>

              <div>
                <span>Tempo</span>
                <strong>
                  {timeframes.length > 0
                    ? timeframes.length
                    : '--'}
                </strong>
              </div>

              <div>
                <span>Última verificação</span>
                <strong>
                  {systemHealth?.last_symbol_update || '--'}
                </strong>
              </div>

              <div>
                <span>Atualização</span>
                <strong>3s</strong>
              </div>
            </div>
          )}
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

            <div className="timeframe-bar">
              {/* Favoritos na barra */}
              {timeframeOptions
                .filter((opt) => favoriteTimeframes.includes(opt.name))
                .map((option) => (
                  <button
                    key={option.name}
                    type="button"
                    className={
                      selectedTimeframe === option.name
                        ? 'timeframe-button active'
                        : 'timeframe-button'
                    }
                    onClick={() => setSelectedTimeframe(option.name)}
                    title={option.name}
                  >
                    {option.name}
                  </button>
                ))}

              {/* Botão de gaveta */}
              <button
                ref={timeframeToggleRef}
                type="button"
                className={
                  timeframeDrawerOpen
                    ? 'timeframe-drawer-toggle active'
                    : 'timeframe-drawer-toggle'
                }
                onClick={() => {
                  setTimeframeDrawerOpen((prev) => {
                    const next = !prev;
                    if (next && timeframeToggleRef.current) {
                      const rect =
                        timeframeToggleRef.current.getBoundingClientRect();
                      setDrawerPopupPos({
                        top: rect.bottom + 6,
                        left: rect.left,
                      });
                    }
                    return next;
                  });
                }}
                title="Todos os timeframes"
              >
                {selectedTimeframe &&
                !favoriteTimeframes.includes(selectedTimeframe)
                  ? selectedTimeframe
                  : '⋯'}
                <span className="timeframe-drawer-arrow">
                  {timeframeDrawerOpen ? '▲' : '▼'}
                </span>
              </button>
            </div>

            {/* Portal: popup renderizado direto no document.body para escapar
                de TODOS os overflow:hidden ancestrais (topbar, workspace).
                Ancorado via position:fixed + coordenadas do botão. */}
            {timeframeDrawerOpen &&
              createPortal(
                <div
                  ref={timeframePopupRef}
                  className="timeframe-drawer-popup"
                  style={{
                    position: 'fixed',
                    top: drawerPopupPos.top,
                    left: drawerPopupPos.left,
                    zIndex: 99999,
                  }}
                >
                  {[
                    {
                      label: 'Minutos',
                      items: timeframeOptions.filter((o) =>
                        o.name.startsWith('M'),
                      ),
                    },
                    {
                      label: 'Horas',
                      items: timeframeOptions.filter((o) =>
                        o.name.startsWith('H'),
                      ),
                    },
                    {
                      label: 'Diário / Superior',
                      items: timeframeOptions.filter(
                        (o) =>
                          !o.name.startsWith('M') &&
                          !o.name.startsWith('H'),
                      ),
                    },
                  ]
                    .filter((group) => group.items.length > 0)
                    .map((group) => (
                      <div
                        key={group.label}
                        className="tf-drawer-group"
                      >
                        <span className="tf-drawer-group-label">
                          {group.label}
                        </span>

                        {group.items.map((opt) => (
                          <div
                            key={opt.name}
                            className="tf-drawer-row"
                          >
                            <button
                              type="button"
                              className={
                                selectedTimeframe === opt.name
                                  ? 'tf-drawer-item active'
                                  : 'tf-drawer-item'
                              }
                              onClick={() => {
                                setSelectedTimeframe(opt.name);
                                setTimeframeDrawerOpen(false);
                              }}
                            >
                              {opt.name}
                            </button>

                            <button
                              type="button"
                              className={
                                favoriteTimeframes.includes(opt.name)
                                  ? 'tf-star active'
                                  : 'tf-star'
                              }
                              onClick={() => {
                                setFavoriteTimeframes((prev) =>
                                  prev.includes(opt.name)
                                    ? prev.filter((f) => f !== opt.name)
                                    : [...prev, opt.name],
                                );
                                setTimeframeDrawerOpen(false);
                              }}
                              title={
                                favoriteTimeframes.includes(opt.name)
                                  ? 'Remover dos favoritos'
                                  : 'Adicionar aos favoritos'
                              }
                            >
                              {favoriteTimeframes.includes(opt.name)
                                ? '★'
                                : '☆'}
                            </button>
                          </div>
                        ))}
                      </div>
                    ))}
                </div>,
                document.body,
              )}
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
                ? 'Conta conectada'
                : 'Conta desconectada'}
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
          {activeView === 'strategies' ? (
            <section className="strategies-workspace p-6 w-full overflow-y-auto">
              <ShadowStrategiesView />
            </section>
          ) : (
            <section className="chart-workspace">
              {activeView === 'dashboard' && (
                <div className="p-4 border-b border-slate-800 bg-slate-950/80">
                  <MarketAlertsSection />
                </div>
              )}
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

                <div className="indicator-toggles flex items-center gap-1.5">
                  <button
                    type="button"
                    className="chart-tool-btn"
                    onClick={() => setIndicatorManagerOpen(true)}
                    title="Gerenciar Indicadores Visuais"
                  >
                    📊 Indicadores
                  </button>
                </div>

                <EvidenceDrawer
                  events={divergenceEvents}
                  onActivateEvidence={handleActivateEvidence}
                />

                <div className="chart-toolbar-status">
                  <span>Dados reais do MetaTrader</span>
                  <strong>{selectedTimeframe}</strong>
                </div>
              </div>

              <div className="chart-stage">
                <MarketChart
                  symbol={selectedSymbol}
                  timeframe={selectedTimeframe}
                  timeframeMap={timeframeMap}
                  refreshInterval={2000}
                  userIndicators={userIndicators}
                  onToggleIndicatorVisibility={handleToggleUserIndicatorVisibility}
                  onRemoveIndicator={handleRemoveUserIndicator}
                  onOpenIndicatorSettings={() => setIndicatorModalOpen(true)}
                  showRSI={showRSI || !!activeEvidenceEventId}
                  showEMA50={showEMA50}
                  showEMA200={showEMA200}
                  showDivergences={showDivergences}
                  activeEvidenceEventId={activeEvidenceEventId}
                  activeEvidenceData={activeEvidenceData}
                  onClearEvidence={() => {
                    setActiveEvidenceEventId(null);
                    setActiveEvidenceData(null);
                  }}
                />
              </div>
            </section>
          )}

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
                      <span>{symbolsAvailable} ativos disponíveis</span>
                    </div>
                    <button
                      type="button"
                      id="watchlist-add-btn"
                      title="Adicionar ativo"
                      onClick={() => setSymbolSearchOpen(true)}
                    >
                      +
                    </button>
                  </div>

                  {/* Busca na watchlist */}
                  <div className="watchlist-search-wrapper">
                    <input
                      type="text"
                      id="watchlist-search-input"
                      className="watchlist-search-input"
                      placeholder="Filtrar watchlist..."
                      value={watchlistSearch}
                      onChange={(e) => setWatchlistSearch(e.target.value)}
                      autoComplete="off"
                    />
                  </div>

                  {loadingWatchlist && (
                    <p className="drawer-message">Carregando watchlist...</p>
                  )}

                  <div className="terminal-watchlist" style={{ overflowY: 'auto', maxHeight: '100%' }}>
                    {watchlistQuotes.length === 0 ? (
                      <div className="drawer-message info">
                        Sua watchlist está vazia. Clique em + acima para buscar e adicionar ativos do catálogo.
                      </div>
                    ) : (
                      watchlistQuotes
                        .filter((market) => {
                          const sym = market.symbol || '';
                          return !watchlistSearch || sym.toLowerCase().includes(watchlistSearch.toLowerCase());
                        })
                        .map((market) => (
                          <div key={market.symbol} className="terminal-watchlist-row-wrapper">
                            <button
                              type="button"
                              className={
                                market.symbol === selectedSymbol
                                  ? 'terminal-watchlist-row selected'
                                  : 'terminal-watchlist-row'
                              }
                              onClick={() => setSelectedSymbol(market.symbol)}
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
                                  {formatPrice(market.bid, market.digits ?? 2)}
                                </strong>
                                <span>Venda {formatPrice(market.ask, market.digits ?? 2)}</span>
                              </div>
                            </button>
                            <button
                              type="button"
                              className="watchlist-remove-btn"
                              title={`Remover ${market.symbol} da watchlist`}
                              onClick={() => handleRemoveFromWatchlist(market.symbol)}
                            >
                              ×
                            </button>
                          </div>
                        ))
                    )}
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
                <div style={{ padding: '8px', overflowY: 'auto', height: '100%' }}>
                  <MarketAlertsSection onNavigateToEvent={handleNavigateToEvent} />
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
            <span>Broker</span>
            <strong>{brokerName}</strong>
          </div>

          <div>
            <span>Corretora</span>
            <strong>{account?.company || '--'}</strong>
          </div>
        </footer>
      </section>

      <HdfToastStack
        toasts={toasts}
        onDismiss={handleDismissToast}
        onNavigate={handleNavigateToEvent}
      />

      {symbolSearchOpen && (
        <SymbolSearchModal
          symbols={symbols.map((s) => ({ symbol: s, name: s, category: 'OTHER' }))}
          watchlist={watchlistQuotes.length > 0 ? watchlistQuotes : markets}
          onAdd={handleAddToWatchlist}
          onClose={() => setSymbolSearchOpen(false)}
        />
      )}

      {indicatorManagerOpen && (
        <IndicatorManagerModal
          activeIndicators={userIndicators}
          onAdd={handleAddUserIndicator}
          onRemove={handleRemoveUserIndicator}
          onToggleVisibility={handleToggleUserIndicatorVisibility}
          onClose={() => setIndicatorManagerOpen(false)}
        />
      )}
    </div>
  );
}

export default App;