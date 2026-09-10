#property script_show_inputs
#property strict

input string ProbeSymbol = "EURUSDxx";
input ENUM_TIMEFRAMES ProbeTimeframe = PERIOD_M15;
input int ProbePeriod = 8;
input int ProbeBars = 512;
input string OutputFile = "HAGMARTK\\ddix_adxwilder_probe.csv";

bool CopyReady(const int handle, MqlRates &rates[], double &adx[], double &plus_di[], double &minus_di[])
  {
   ArraySetAsSeries(rates,true);
   ArraySetAsSeries(adx,true);
   ArraySetAsSeries(plus_di,true);
   ArraySetAsSeries(minus_di,true);

   int rate_count=CopyRates(ProbeSymbol,ProbeTimeframe,0,ProbeBars,rates);
   if(rate_count<=0)
      return false;
   if(BarsCalculated(handle)<rate_count)
      return false;
   if(CopyBuffer(handle,MAIN_LINE,0,rate_count,adx)!=rate_count)
      return false;
   if(CopyBuffer(handle,PLUSDI_LINE,0,rate_count,plus_di)!=rate_count)
      return false;
   if(CopyBuffer(handle,MINUSDI_LINE,0,rate_count,minus_di)!=rate_count)
      return false;
   return true;
  }

void OnStart()
  {
   if(ProbePeriod<=0 || ProbeBars<32)
     {
      Print("DDIX_PROBE_INVALID_INPUT");
      return;
     }
   if(!SymbolSelect(ProbeSymbol,true))
     {
      Print("DDIX_PROBE_SYMBOL_SELECT_FAILED ",ProbeSymbol);
      return;
     }

   int handle=iADXWilder(ProbeSymbol,ProbeTimeframe,ProbePeriod);
   if(handle==INVALID_HANDLE)
     {
      Print("DDIX_PROBE_HANDLE_FAILED ",GetLastError());
      return;
     }

   MqlRates rates[];
   double adx[],plus_di[],minus_di[];
   bool ready=false;
   for(int attempt=0; attempt<120; ++attempt)
     {
      if(CopyReady(handle,rates,adx,plus_di,minus_di))
        {
         ready=true;
         break;
        }
      Sleep(500);
     }
   if(!ready)
     {
      Print("DDIX_PROBE_DATA_NOT_READY ",GetLastError());
      IndicatorRelease(handle);
      return;
     }

   int file=FileOpen(OutputFile,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(file==INVALID_HANDLE)
     {
      Print("DDIX_PROBE_FILE_OPEN_FAILED ",GetLastError());
      IndicatorRelease(handle);
      return;
     }

   FileWrite(file,"symbol","timeframe","period","time","high","low","close","adx","plus_di","minus_di");
   int count=ArraySize(rates);
   for(int i=count-1; i>=0; --i)
     {
      if(adx[i]==EMPTY_VALUE || plus_di[i]==EMPTY_VALUE || minus_di[i]==EMPTY_VALUE)
         continue;
      FileWrite(file,
                ProbeSymbol,
                EnumToString(ProbeTimeframe),
                ProbePeriod,
                TimeToString(rates[i].time,TIME_DATE|TIME_MINUTES),
                DoubleToString(rates[i].high,_Digits),
                DoubleToString(rates[i].low,_Digits),
                DoubleToString(rates[i].close,_Digits),
                DoubleToString(adx[i],10),
                DoubleToString(plus_di[i],10),
                DoubleToString(minus_di[i],10));
     }
   FileFlush(file);
   FileClose(file);
   IndicatorRelease(handle);
   Print("DDIX_PROBE_OK rows=",count," file=",OutputFile);
  }
