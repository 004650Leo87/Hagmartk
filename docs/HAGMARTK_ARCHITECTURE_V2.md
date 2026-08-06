# Hagmartk Architecture v2

## 1. Vision

Hagmartk is a modular financial intelligence platform focused on transforming real market data into robust trading insights, operational signals, and research-grade analytics. The platform is designed to grow from a live market data explorer and charting dashboard into a full quantitative ecosystem with backtesting, strategy validation, automation, and marketplace capabilities.

## 2. Mission

Build a professional system that combines market data ingestion, statistical validation, decision support, and visual analytics into a coherent platform. Every strategy and signal must be based on real market data, scientifically validated, and operationally actionable.

## 3. Core Principles

- Use only real market data; no synthetic or fictitious data.
- Avoid randomness unless explicitly part of an algorithmic experiment.
- Report only statistically verifiable results.
- Design modules independently so each can evolve without breaking the whole system.
- Start with free and accessible tools wherever possible.
- Keep code organized, readable, and documented.
- Build with a data-first mindset: analytics and decisions must be reproducible.

## 4. System Architecture

Hagmartk is organized as a multi-layered platform:

- **API Backend**: Python FastAPI service exposing market, account, and analytics endpoints.
- **Frontend**: React + Vite application for visualization, dashboards, and chart interactions.
- **Engine**: Quantitative and backtesting engine targeted for strategy validation and execution.
- **MT5 Integration**: Real market data ingestion from MetaTrader 5 for quotes, candles, account state, and trade history.
- **Persistence & State**: Local browser persistence for chart views; future persistence layers for strategies, backtests, and user metadata.

## 5. Backend Architecture

### Current Implementation

- **`backend/api/main.py`**: FastAPI server bootstrap for local development.
- **`backend/api/app.py`**: Application initialization and CORS configuration.
- **`backend/api/routes.py`**: HTTP routes for market and account data.
- **`backend/services/mt5_service.py`**: MT5 connection lifecycle management.
- **`backend/services/market_service.py`**: Symbol lookup, quote retrieval, and OHLC candle loading.
- **`backend/services/account_service.py`**: Account info, open positions, daily history, and summary computations.
- **`backend/core/config.py`**: Application paths and global settings.
- **`backend/core/logger.py`**: Logging configuration and log file management.

### Design Characteristics

- The backend is currently API-first and tightly coupled to MetaTrader 5.
- Business logic is separated into service classes to isolate MT5 interaction.
- Empty modules exist for future expansion: auth, dependencies, schemas, backtest service, strategy service, and database.

## 6. Frontend Architecture

### Current Implementation

- **`frontend/src/main.jsx`**: React render entrypoint.
- **`frontend/src/App.jsx`**: Main dashboard shell and API orchestration.
- **`frontend/src/components/MarketChart.jsx`**: Chart component with lifecycle and viewport persistence logic.
- **`frontend/src/services/api.js`**: Client functions for backend endpoints.
- **`frontend/src/chart/*`**: Reusable chart utilities for Lightweight Charts integration.

### Chart Engine

- Uses `lightweight-charts` to render candlestick charts.
- Supports symbol/timeframe selection and viewport preservation between sessions.
- Separates concerns across chart creation, data preparation, navigation, persistence, and event handling.

## 7. Engine Architecture

### Current Implementation

- **`engine/backtest.py`** exists as a separate engine module, currently minimal.
- The backend contains placeholders for `backtest_service.py` and `strategy_service.py`, which will eventually implement strategy evaluation and simulation.

### Future Engine Goals

- Introduce a dedicated backtesting core capable of ingesting candle streams and executing strategy logic.
- Add strategy validation and score computation pipelines.
- Enable pluggable engines for market, analysis, and decision modules.

## 8. AI Architecture

### Current State

- No active AI module is implemented yet.
- Roadmap envisions a future AI layer for signal generation, analytics, and intelligent automation.

### Future Objectives

- Create an AI Engine that can provide:
  - feature selection and pattern detection,
  - strategy recommendation,
  - natural-language summaries and alerts,
  - risk management guidance.
- Integrate AI modules as optional services without blocking core market and backtesting functionality.

## 9. Data Flow

### Current Flow

1. Frontend requests data from backend API.
2. Backend routes call service layer classes.
3. Service classes connect to MetaTrader 5 and retrieve live data.
4. Backend normalizes raw MT5 responses into JSON and returns them.
5. Frontend converts JSON candles into Lightweight Charts data and renders the chart.
6. User viewport preferences are saved in browser `localStorage`.

### Key Data Paths

- **Market data**: `MarketService` → MT5 `symbol_info_tick`, `copy_rates_from_pos` → frontend chart.
- **Account data**: `AccountService` → MT5 account, position, deal history → dashboard summaries.

## 10. Development Roadmap

### Phase 1: Core Market and Charting

- Complete MT5 market data ingestion endpoints.
- Build a reliable charting and dashboard experience.
- Stabilize frontend/backend communication.

### Phase 2: Backtesting and Strategy Layer

- Implement `backend/services/backtest_service.py`.
- Implement `backend/services/strategy_service.py`.
- Add Pydantic schemas for strategy, market, and backtest models.
- Build engine integration with `engine/backtest.py`.

### Phase 3: Validation, AI, and Automation

- Add statistical validation and performance metrics.
- Build AI architecture for analytics, signal recommendations, and natural-language alerts.
- Add account automation and trade execution support.

### Phase 4: Production Platform

- Add authentication and authorization.
- Add marketplace, licensing, and strategy sharing.
- Build a professional web dashboard and alerting ecosystem.

## 11. Folder Organization

- **`backend/`**: API, business services, MT5 integration, and core utilities.
  - `api/`: FastAPI entry points, routes, auth, and dependency injection.
  - `services/`: service classes for market, account, backtest, strategy, and MT5 access.
  - `core/`: configuration, logging, database abstraction, exceptions, security.
  - `schemas/`: future Pydantic models.
- **`frontend/`**: React UI, charting logic, state, and API client.
  - `src/components/`: reusable UI components.
  - `src/services/`: API integration functions.
  - `src/chart/`: chart engine abstractions and utilities.
  - `src/state/`: future shared state management.
- **`engine/`**: domain engine logic for backtesting and quantitative analysis.
- **`docs/`**: architecture and planning documents.
- **`data/`**: external or sample data storage.
- **`database/`**: persistence files or future database artifacts.
- **`strategies/`**: strategy definitions and models.

## 12. Coding Standards

- Use clear naming and single responsibility for modules.
- Keep API route controllers thin; push business logic into services.
- Organize frontend state separately from UI components.
- Prefer simple, explicit error handling and clear exception messages.
- Keep chart state persistence deterministic and user-centric.
- Document each module and maintain architecture docs alongside code.
- Use consistent formatting in Python and JavaScript.

## 13. Future Modules

- **Authentication & Authorization**: user accounts, API tokens, role-based access.
- **Strategy Marketplace**: repository for strategy definitions and sharing.
- **Licensing and licensing validation**: usage control and compliance.
- **Statistical Validator**: rigorous metrics, probability analysis, and edge-case testing.
- **Alerting Engine**: notifications via Telegram, email, or other channels.
- **Execution Engine**: trade automation with broker and MT5 order management.
- **Dataset Manager**: data versioning, history snapshots, and instrument metadata.

## 14. Long-term Vision

Hagmartk becomes a production-grade, modular financial intelligence system that supports research, validation, execution, and monitoring in a single ecosystem. It should offer a professional dashboard, live market intelligence, algorithmic validation, and a trusted platform for traders and researchers to build, test, and deploy statistically sound strategies.
