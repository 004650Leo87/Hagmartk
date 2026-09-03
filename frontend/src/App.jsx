import React, { Component, useEffect, useRef, useState } from 'react';
import './App.css';
import TopCommandBar from './components/TopCommandBar';
import LeftNavigation from './components/LeftNavigation';
import BottomStatusBar from './components/BottomStatusBar';
import ContextPanel from './components/ContextPanel';
import MarketChart from './components/MarketChart';
import ShadowStrategiesView from './components/ShadowStrategiesView';
import WatchlistView from './components/WatchlistView';
import StrategyCenterView from './components/StrategyCenterView';
import BacktestView from './components/BacktestView';
import AiInsightsView from './components/AiInsightsView';
import AutomationSafetyView from './components/AutomationSafetyView';
import AlertCenterDrawer from './components/AlertCenterDrawer';
import HdfToastStack from './components/HdfToastStack';
import SymbolSearchModal from './components/SymbolSearchModal';
import IndicatorManagerModal from './components/IndicatorManagerModal';

import {
  getShadowRecentEvents,
  getHDFRecentEvidences,
  getShadowScanners,
  getSystemHealth,
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
} from './services/api';

// Error Boundary Component to protect against Black Screen failures
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Hagmartk Module Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="hk-error-compact">
          <span className="hk-error-compact-icon">⚠️</span>
          <span className="hk-error-compact-text">{this.props.name || 'Módulo'}: Indisponível</span>
          <button
            type="button"
            className="hk-error-compact-retry"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Tentar Novamente
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  // Application State
  const [activeTab, setActiveTab] = useState('chart'); // 'chart' | 'watchlist' | 'shadow' | 'strategies' | 'backtest' | 'ai' | 'automation' | 'alerts' | 'settings'
  const [navExpanded, setNavExpanded] = useState(false);
  
  const [symbol, setSymbol] = useState('XAUUSD');
  const [timeframe, setTimeframe] = useState('H1');
  
  // Context Panel & Modals
  const [contextMode, setContextMode] = useState('watchlist'); // 'watchlist' | 'evidence' | 'settings' | 'system'
  const [isContextOpen, setIsContextOpen] = useState(true);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isIndicatorsOpen, setIsIndicatorsOpen] = useState(false);
  const [isAlertsOpen, setIsAlertsOpen] = useState(false);

  // Zen / Focus Mode
  const [isZenMode, setIsZenMode] = useState(false);

  // Bottom Drawer State
  const [isBottomDrawerOpen, setIsBottomDrawerOpen] = useState(false);
  const [bottomDrawerTab, setBottomDrawerTab] = useState('POSITIONS');

  // Data States
  const [watchlistData, setWatchlistData] = useState([]);
  const [shadowEvents, setShadowEvents] = useState([]);
  const [hdfEvidences, setHdfEvidences] = useState([]);
  const [hdfToasts, setHdfToasts] = useState([]);
  const seenEvidenceIdsRef = useRef(new Set());
  const evidenceBaselineLoadedRef = useRef(false);
  const [systemStatus, setSystemStatus] = useState('UNKNOWN');
  const [systemHealth, setSystemHealth] = useState(null);
  const [activeEvidence, setActiveEvidence] = useState(null);
  const [operationalCount, setOperationalCount] = useState(39);

  // Theme State ('black-piano' | 'flight-deck-light')
  const [theme, setTheme] = useState(() => localStorage.getItem('hk_theme') || 'black-piano');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('hk_theme', theme);
  }, [theme]);

  const [showRSI, setShowRSI] = useState(true);
  const [indicators, setIndicators] = useState({
    ema20: true,
    ema50: true,
    ema200: false,
    rsi: true,
  });

  // Global Keyboard Shortcuts (Ctrl+K for search)
  useEffect(() => {
    function handleKeyDown(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Load Watchlist & System Data
  useEffect(() => {
    async function loadData() {
      try {
        const wl = await getWatchlist();
        setWatchlistData(wl || []);
      } catch (err) {
        console.error('Erro ao carregar watchlist:', err);
      }

      try {
        const health = await getSystemHealth();
        setSystemHealth(health);
        const isOnline = Boolean(health?.adapter_connected || health?.terminal_status);
        setSystemStatus(isOnline ? 'ONLINE' : 'DEGRADED');
      } catch (err) {
        console.error('Erro ao carregar saúde do sistema:', err);
        setSystemHealth(null);
        setSystemStatus('DEGRADED');
      }

      try {
        const scanners = await getShadowScanners();
        if (Array.isArray(scanners)) {
          const running = scanners.filter((s) => s.status === 'RUNNING').length;
          setOperationalCount(running);
        }
      } catch (err) {
        console.error('Erro ao carregar scanners Shadow:', err);
      }

      try {
        const recent = await getShadowRecentEvents(20);
        setShadowEvents(recent?.toast_events || recent?.events || []);
      } catch (err) {
        console.error('Erro ao carregar eventos Shadow:', err);
      }

      try {
        const recentEvidence = await getHDFRecentEvidences(100);
        const live = (recentEvidence?.evidences || []).filter((ev) => !ev.is_test);
        setHdfEvidences(live);

        const currentIds = new Set(live.map((ev) => ev.evidence_id));
        if (evidenceBaselineLoadedRef.current) {
          const newDvp = live.filter((ev) => ev.variant_stage === 'HDF_DVP' && !seenEvidenceIdsRef.current.has(ev.evidence_id));
          if (newDvp.length) {
            setHdfToasts((prev) => [
              ...newDvp.map((ev) => ({ ...ev, id: ev.evidence_id, status_code: 'HDF_DVP', event_time: ev.detected_at || ev.created_at })),
              ...prev,
            ].slice(0, 8));
          }
        } else {
          evidenceBaselineLoadedRef.current = true;
        }
        seenEvidenceIdsRef.current = currentIds;
      } catch (err) {
        console.error('Erro ao carregar evidências HDF:', err);
      }
    }
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'black-piano' ? 'flight-deck-light' : 'black-piano'));
  };

  const handleToggleZenMode = () => {
    setIsZenMode((prev) => {
      const next = !prev;
      if (next) {
        setIsContextOpen(false);
        setNavExpanded(false);
        setIsBottomDrawerOpen(false);
      } else {
        setIsContextOpen(true);
      }
      return next;
    });
  };

  const handleSelectSymbol = (newSymbol) => {
    setSymbol(newSymbol);
    setIsSearchOpen(false);
  };

  const handleAddWatchlist = async (sym) => {
    try {
      const res = await addToWatchlist(sym);
      setWatchlistData(res.symbols || []);
    } catch (err) {
      console.error('Erro ao adicionar ativo:', err);
    }
  };

  const handleRemoveWatchlist = async (sym) => {
    try {
      const res = await removeFromWatchlist(sym);
      setWatchlistData(res.symbols || []);
    } catch (err) {
      console.error('Erro ao remover ativo:', err);
    }
  };

  const handleToggleIndicator = (key) => {
    setIndicators((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <ErrorBoundary name="APPLICATION SHELL">
      <div className={`hk-app-container ${theme} ${isZenMode ? 'zen-mode' : ''}`}>
        {/* 1. TOP FLIGHT COMMAND BAR */}
        <ErrorBoundary name="TOP COMMAND BAR">
          <TopCommandBar
            selectedSymbol={symbol}
            onSelectSymbolClick={() => setIsSearchOpen(true)}
            timeframe={timeframe}
            onSelectTimeframe={setTimeframe}
            onOpenIndicators={() => setIsIndicatorsOpen(true)}
            onToggleEvidenceCard={() => {
              setContextMode('evidence');
              setIsContextOpen(true);
            }}
            hasEvidence={Boolean(activeEvidence)}
            showRSI={showRSI}
            onToggleRSI={() => setShowRSI((prev) => !prev)}
            onToggleAlerts={() => setIsAlertsOpen(true)}
            alertCount={shadowEvents.length + hdfEvidences.filter((ev) => ev.variant_stage === 'HDF_DVP').length}
            systemStatus={systemStatus}
            systemHealth={systemHealth}
            theme={theme}
            onToggleTheme={handleToggleTheme}
            isZenMode={isZenMode}
            onToggleZen={handleToggleZenMode}
            operationalCount={operationalCount}
            totalCount={39}
          />
        </ErrorBoundary>

        {/* 2. MAIN WORKSPACE */}
        <div className="hk-workspace-body">
          {/* LEFT FLIGHT RAIL */}
          {!isZenMode && (
            <ErrorBoundary name="LEFT FLIGHT RAIL">
              <LeftNavigation
                activeTab={activeTab}
                onSelectTab={setActiveTab}
                isExpanded={navExpanded}
                onToggleExpand={() => setNavExpanded((prev) => !prev)}
              />
            </ErrorBoundary>
          )}

          {/* PRIMARY WORKSPACE */}
          <main className="hk-main-workspace">
            {activeTab === 'chart' && (
              <ErrorBoundary name="PRIMARY MARKET DISPLAY">
                <MarketChart
                  symbol={symbol}
                  timeframe={timeframe}
                  showRSI={showRSI}
                  onToggleRSI={() => setShowRSI((prev) => !prev)}
                  theme={theme}
                  activeEvidenceData={activeEvidence}
                  onClearEvidence={() => setActiveEvidence(null)}
                />
              </ErrorBoundary>
            )}

            {activeTab === 'watchlist' && (
              <div className="hk-page-view">
                <ErrorBoundary name="WATCHLIST & CATALOG">
                  <WatchlistView
                    watchlist={watchlistData}
                    onSelectSymbol={(sym) => {
                      setSymbol(sym);
                      setActiveTab('chart');
                    }}
                    onAddToWatchlist={handleAddWatchlist}
                    onRemoveFromWatchlist={handleRemoveWatchlist}
                  />
                </ErrorBoundary>
              </div>
            )}

            {activeTab === 'shadow' && (
              <div className="hk-page-view">
                <ErrorBoundary name="SHADOW MONITOR">
                  <ShadowStrategiesView />
                </ErrorBoundary>
              </div>
            )}

            {activeTab === 'strategies' && (
              <div className="hk-page-view">
                <ErrorBoundary name="HDF STRATEGY CENTER">
                  <StrategyCenterView />
                </ErrorBoundary>
              </div>
            )}

            {activeTab === 'backtest' && (
              <div className="hk-page-view">
                <ErrorBoundary name="BACKTEST LAB">
                  <BacktestView />
                </ErrorBoundary>
              </div>
            )}

            {activeTab === 'ai' && (
              <div className="hk-page-view">
                <ErrorBoundary name="IA HAGMARTK">
                  <AiInsightsView />
                </ErrorBoundary>
              </div>
            )}

            {activeTab === 'automation' && (
              <div className="hk-page-view">
                <ErrorBoundary name="AUTOMATION SAFETY">
                  <AutomationSafetyView />
                </ErrorBoundary>
              </div>
            )}

            {activeTab === 'alerts' && (
              <div className="hk-page-view">
                <ErrorBoundary name="ALERTS CENTER">
                  <ShadowStrategiesView />
                </ErrorBoundary>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="hk-page-view">
                <ErrorBoundary name="SETTINGS">
                  <StrategyCenterView />
                </ErrorBoundary>
              </div>
            )}
          </main>

          {/* RIGHT MFD CONTEXT DISPLAY (Rendered in Chart mode or when evidence active) */}
          {isContextOpen && !isZenMode && (activeTab === 'chart' || contextMode === 'evidence') && (
            <ErrorBoundary name="RIGHT CONTEXT DISPLAY">
              <ContextPanel
                mode={contextMode}
                onSelectMode={setContextMode}
                onClose={() => setIsContextOpen(false)}
                watchlist={watchlistData}
                selectedSymbol={symbol}
                onSelectSymbol={(sym) => {
                  setSymbol(sym);
                  setActiveTab('chart');
                }}
                onRemoveFromWatchlist={handleRemoveWatchlist}
                onAddToWatchlistClick={() => setIsSearchOpen(true)}
                evidenceData={activeEvidence}
                indicators={indicators}
                onToggleIndicator={handleToggleIndicator}
                systemStatus={systemStatus}
                systemHealth={systemHealth}
                operationalCount={operationalCount}
                totalCount={39}
              />
            </ErrorBoundary>
          )}
        </div>

        {/* 3. COMPACT BOTTOM STATUS BAR & COLLAPSIBLE DRAWER */}
        {!isZenMode && (
          <ErrorBoundary name="BOTTOM STATUS BAR">
            <BottomStatusBar
              mt5Connected={systemStatus === 'ONLINE'}
              shadowStatus="RUNNING"
              operationalCount={operationalCount}
              totalCount={39}
              isDrawerOpen={isBottomDrawerOpen}
              onToggleDrawer={() => setIsBottomDrawerOpen((prev) => !prev)}
              activeDrawerTab={bottomDrawerTab}
              onSelectDrawerTab={setBottomDrawerTab}
            />
          </ErrorBoundary>
        )}

        {/* MODALS & DRAWERS */}
        {isSearchOpen && (
          <SymbolSearchModal
            onClose={() => setIsSearchOpen(false)}
            onSelectSymbol={handleSelectSymbol}
          />
        )}

        {isIndicatorsOpen && (
          <IndicatorManagerModal
            onClose={() => setIsIndicatorsOpen(false)}
            userIndicators={[]}
            onSaveUserIndicators={() => {}}
          />
        )}

        <HdfToastStack
          toasts={hdfToasts}
          onDismiss={(id) => setHdfToasts((prev) => prev.filter((item) => item.id !== id))}
          onNavigate={(ev) => {
            if (ev.symbol) setSymbol(ev.symbol);
            if (ev.timeframe) setTimeframe(ev.timeframe);
            setActiveEvidence(ev);
            setContextMode('evidence');
            setIsContextOpen(true);
            setActiveTab('chart');
          }}
        />

        <AlertCenterDrawer
          isOpen={isAlertsOpen}
          onClose={() => setIsAlertsOpen(false)}
          events={shadowEvents}
          evidences={hdfEvidences}
          selectedEventId={activeEvidence?.evidence_id || activeEvidence?.event_id || activeEvidence?.id}
          onSelectEvent={(evt) => {
            if (evt.symbol) setSymbol(evt.symbol);
            if (evt.timeframe) setTimeframe(evt.timeframe);
            setActiveEvidence(evt);
            setContextMode('evidence');
            setIsContextOpen(true);
            setActiveTab('chart');
          }}
        />
      </div>
    </ErrorBoundary>
  );
}