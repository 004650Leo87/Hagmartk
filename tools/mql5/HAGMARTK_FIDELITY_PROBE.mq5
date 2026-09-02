#property script_show_inputs
#property strict

input int InpATRPeriod = 14;

void OnStart()
{
   int handle = iATR(_Symbol, _Period, InpATRPeriod);
   double atr[1];
   ResetLastError();
   int copied = (handle == INVALID_HANDLE) ? -1 : CopyBuffer(handle, 0, 0, 1, atr);
   int err = GetLastError();

   MqlTick tick;
   bool tick_ok = SymbolInfoTick(_Symbol, tick);
   datetime now = TimeCurrent();
   datetime trade_server = TimeTradeServer();
   datetime bar0 = iTime(_Symbol, _Period, 0);
   int bars = Bars(_Symbol, _Period);
   int calculated = (handle == INVALID_HANDLE) ? -1 : BarsCalculated(handle);

   string file = "HAGMARTK_FIDELITY_PROBE.csv";
   int fh = FileOpen(file, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ';');
   if(fh == INVALID_HANDLE) { Print("HAGMARTK_PROBE file error=", GetLastError()); return; }
   FileSeek(fh, 0, SEEK_END);
   FileWrite(fh,
      TimeToString(now, TIME_DATE|TIME_SECONDS),
      (long)now,
      TimeToString(trade_server, TIME_DATE|TIME_SECONDS),
      (long)trade_server,
      TimeToString(bar0, TIME_DATE|TIME_SECONDS),
      (long)bar0,
      _Symbol,
      EnumToString(_Period),
      bars,
      calculated,
      copied,
      copied > 0 ? DoubleToString(atr[0], _Digits) : "NA",
      err,
      tick_ok ? DoubleToString(tick.bid, _Digits) : "NA",
      tick_ok ? DoubleToString(tick.ask, _Digits) : "NA",
      tick_ok ? (long)tick.time : 0);
   FileClose(fh);
   if(handle != INVALID_HANDLE) IndicatorRelease(handle);
   Print("HAGMARTK_PROBE read-only capture complete: ", file);
}
