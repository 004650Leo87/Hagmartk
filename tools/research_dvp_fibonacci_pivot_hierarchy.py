from collections import Counter
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.engines.market.mt5_market_adapter import MT5MarketAdapter
from backend.strategies.divap.detectors import PivotDetector
from backend.strategies.hdf.prospective_fibonacci import ConfirmedPivot, audit_strict_pre_reversal_leg
from backend.strategies.hdf.strategy import HDFStrategy

SYMBOLS = ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","NZDUSD","USDCAD","EURJPY","GBPJPY","XAUUSD","XAGUSD","BTCUSD","ETHUSD"]
TIMEFRAMES = ["M5","M15","M30","H1","H2","H4"]
WINDOWS = {"MICRO_2_2": 2, "STRUCTURAL_5_5": 5}

def pivots(df, width):
    highs, lows = PivotDetector(pivot_left=width, pivot_right=width).find_pivots(df)
    return sorted([ConfirmedPivot(p.index,p.price,p.is_high,p.confirmed_at_index) for p in highs+lows], key=lambda p:p.index)

def main():
    rows=[]; adapter=MT5MarketAdapter(); adapter.connect()
    try:
        for symbol in SYMBOLS:
            for timeframe in TIMEFRAMES:
                df=pd.DataFrame(adapter.get_candles(symbol,timeframe,count=1200))
                occurrences=HDFStrategy(variant="HDF_DVP").evaluate_full_dataset_analysis(df,symbol,timeframe)["occurrences"]
                pivot_sets={name:pivots(df,width) for name,width in WINDOWS.items()}
                for o in occurrences:
                    decision=df.index[df.time.astype(str)==str(o.temporal_model.confluence_completed_at)].tolist()
                    p2=df.index[df.time.astype(str)==str(o.temporal_model.pivot_2_time)].tolist()
                    if not decision or not p2: continue
                    statuses=[]
                    for name in WINDOWS:
                        r=audit_strict_pre_reversal_leg(direction=o.direction,pivots=pivot_sets[name],decision_index=decision[0],reversal_pivot_index=p2[0],candle_low=float(df.iloc[decision[0]].low),candle_high=float(df.iloc[decision[0]].high))
                        statuses.append(r.status)
                    rows.append((symbol,timeframe,*statuses))
    finally:
        adapter.disconnect()
    print("N",len(rows))
    for idx,name in enumerate(WINDOWS,start=2): print(name,Counter(r[idx] for r in rows))
    print("OVERLAP",Counter((r[2],r[3]) for r in rows))
    for tf in TIMEFRAMES: print(tf, *(Counter(r[i] for r in rows if r[1]==tf) for i in (2,3)))

if __name__ == "__main__": main()
