# HAGMARTK DVP — Deep Source Research — 2026-09-03

Status: SOURCE RESEARCH / IMPLEMENTATION HOLD ON FIB ANCHOR POLICY

## Sources located
1. Fernando Pereira CNPI, *Análise Técnica Aplicada para Traders e Investidores* (public copy).
2. Fernando Pereira, full DIVAP video: *A MELHOR ESTRATÉGIA DE TRADE DA ATUALIDADE - DIVAP*.
3. Horistic public DIVAP material used only as corroboration, not performance evidence.

## Source-backed strategy contract
- RSI/IFR: 14 periods in the full-video explanation.
- DIVAP uses IFR divergence, volume, Fibonacci extension and reversal pattern.
- Source PDF defines Fibonacci setup levels: 61.8%, 100%, 161.8%, 200%, 261.8%.
- Volume must be above its 20-period average.
- Reversal may be graphical or candlestick; video explicitly demonstrates hammer, shooting star and bullish/bearish engulfing.
- Buy activation is above reversal-pattern high; sell activation below pattern low.
- Stop is below the pattern for buys and above it for sells.
- Method is described as usable across markets; H1/H4/D1 are described as more effective, not exclusive.

## New Fibonacci finding
The full video materially narrows the manual construction:
- around 06:34, the example traces the extension from a minimum to a maximum and repeats the maximum as the third point;
- the explanation first uses extrema before the reversal;
- around 07:39 it explicitly presents alternative valid constructions using extrema before or after reversal;
- around 08:03 the post-reversal construction is presented as a shorter/lower-risk alternative;
- around 13:23 a higher-timeframe Fibonacci target can be used as context for a lower-timeframe DIVAP.

This confirms the extension mathematics already implemented, but it does **not** establish one unique automatic swing-selection algorithm for all charts.

## Important correction to automation model
A complete automated HAGMARTK DVP must distinguish:
1. `SOURCE_CONTRACT`: the four mandatory confluences and trade activation/stop rules above.
2. `FIB_CONSTRUCTION_MODE`: which source-described Fibonacci construction is being evaluated.
3. `SWING_SELECTION_POLICY`: deterministic machine rule that maps candles to the extrema used by that construction.

The source documents describe (1) and multiple legitimate forms of (2), but public evidence inspected so far does not uniquely specify (3).
Therefore no hidden retrospective best-fit swing selection is permitted.

## Implementation decision
Do not promote `latest completed leg` as the original DIVAP rule.
Do not weaken the four-confluence gate.
Do not hardcode assets or providers.

Next research implementation must model source-described Fibonacci construction modes explicitly and test each prospectively on the same normalized candle contract. A mode may only become HAGMARTK DVP production policy after its swing-selection rule is deterministic, forward-knowable, provider-neutral and validated against source-demonstrated examples plus real prospective evidence.

## Evidence boundary
Marketing claims about hit rate, ROI or number of trades are not accepted as HAGMARTK performance evidence. HAGMARTK statistics must come from its own replay/shadow/prospective ledger.
