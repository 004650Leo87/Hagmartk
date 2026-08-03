import './App.css';
function App() {
  return (
    <div className="app">
      <header className="topbar">
        <h1>Hagmartk</h1>

        <div className="status">
          🟢 MetaTrader Conectado
        </div>
      </header>

      <main className="dashboard">

        <div className="card">
          <h2>Conta</h2>
          <p>Saldo: --</p>
          <p>Patrimônio: --</p>
        </div>

        <div className="card">
          <h2>Mercado</h2>
          <p>XAUUSD</p>
          <p>BTCUSD</p>
          <p>EURUSD</p>
        </div>

        <div className="card">
          <h2>Estratégias</h2>
          <p>Backtest</p>
          <p>IA</p>
          <p>Automação</p>
        </div>

      </main>
    </div>
  );
}

export default App;