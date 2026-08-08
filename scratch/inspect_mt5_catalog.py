from __future__ import annotations

import sys
import os
import time
import argparse
import json
import MetaTrader5 as mt5
import pandas as pd

# ==============================================================
# FASE A: Probe leve (10 candles) — rápido para TODOS os 117
# FASE B: Histórico completo — SOMENTE para candidatos da cesta
# ==============================================================

PROBE_BARS = 10  # volume mínimo para testar disponibilidade

def categorize_symbol(symbol_name: str, path: str) -> str:
    path_lower = path.lower()
    sym_upper = symbol_name.upper()
    if "forex" in path_lower or "fx" in path_lower:
        return "FOREX"
    elif "metal" in path_lower or "gold" in path_lower or "silver" in path_lower or "xau" in sym_upper or "xag" in sym_upper:
        return "METALS"
    elif "energ" in path_lower or "oil" in path_lower or "brent" in sym_upper or "wti" in sym_upper or "xti" in sym_upper or "xbr" in sym_upper:
        return "ENERGY"
    elif "indic" in path_lower or "index" in path_lower or "us500" in sym_upper or "us30" in sym_upper or "ustec" in sym_upper:
        return "INDICES"
    elif "crypto" in path_lower or "btc" in sym_upper or "eth" in sym_upper:
        return "CRYPTO"
    elif "stock" in path_lower or "equit" in path_lower or "share" in path_lower:
        return "STOCKS"
    return "OTHER"


def run_phase_a(symbols_to_process, num_to_process):
    """FASE A: Probe rápido (10 candles) para todos os símbolos."""
    results = []
    summary = {
        "processed": 0,
        "d1_probe_ok": 0,
        "no_d1_history": 0,
        "inactive": 0,
        "errors": 0,
        "categories": {k: 0 for k in ("FOREX", "METALS", "ENERGY", "INDICES", "CRYPTO", "STOCKS", "OTHER")},
    }

    for idx, s in enumerate(symbols_to_process, 1):
        t0 = time.time()
        sym_name = s.name
        cat = categorize_symbol(sym_name, s.path)
        summary["processed"] += 1
        summary["categories"][cat] += 1

        is_active = (s.trade_mode != mt5.SYMBOL_TRADE_MODE_DISABLED)
        if not is_active:
            summary["inactive"] += 1

        print(f"[{idx}/{num_to_process}] {sym_name:<15} ({cat:<7}) — consultando...", end="  ", flush=True)

        status = "UNKNOWN"
        probe_candles = 0

        try:
            probe = mt5.copy_rates_from_pos(sym_name, mt5.TIMEFRAME_D1, 0, PROBE_BARS)
            if probe is not None and len(probe) > 0:
                probe_candles = len(probe)
                status = "PROBE_OK"
                summary["d1_probe_ok"] += 1
            else:
                status = "NO_HISTORY"
                summary["no_d1_history"] += 1
        except Exception as err:
            status = f"ERROR"
            summary["errors"] += 1

        elapsed = time.time() - t0
        print(f"{status:<12} — probe={probe_candles} bars — {elapsed:.2f}s")
        sys.stdout.flush()

        results.append({
            "symbol": sym_name,
            "description": s.description,
            "category": cat,
            "path": s.path,
            "visible": s.visible,
            "trade_mode": s.trade_mode,
            "is_active": is_active,
            "status": status,
        })

    return results, summary


def run_phase_b_for_candidates(candidates):
    """FASE B: Histórico completo (10.000 candles) SOMENTE para candidatos confirmados."""
    detailed = []
    print(f"\n=== FASE B: Buscando histórico completo de {len(candidates)} candidatos ===\n")
    sys.stdout.flush()

    for idx, sym_name in enumerate(candidates, 1):
        t0 = time.time()
        print(f"[{idx}/{len(candidates)}] {sym_name:<15} — buscando histórico completo...", end="  ", flush=True)

        cnt = 0
        first_c = "N/A"
        last_c = "N/A"
        status = "UNKNOWN"

        try:
            rates = mt5.copy_rates_from_pos(sym_name, mt5.TIMEFRAME_D1, 0, 10000)
            if rates is not None and len(rates) > 0:
                cnt = len(rates)
                first_c = pd.to_datetime(rates[0]["time"], unit="s").strftime("%Y-%m-%d")
                last_c = pd.to_datetime(rates[-1]["time"], unit="s").strftime("%Y-%m-%d")
                status = "OK"
            else:
                status = "NO_HISTORY"
        except Exception as err:
            status = "ERROR"

        elapsed = time.time() - t0
        print(f"{status:<10} — {cnt:>5} candles — Range: {first_c} ate {last_c} — {elapsed:.2f}s")
        sys.stdout.flush()

        detailed.append({
            "symbol": sym_name,
            "status": status,
            "candle_count": cnt,
            "first_candle": first_c,
            "last_candle": last_c,
        })

    return detailed


def inspect_catalog(limit: int = 0, phase_b_symbols=None):
    start_total_time = time.time()
    print("=== INSPEÇÃO MT5 — FASE A (PROBE RÁPIDO) ===\n")
    sys.stdout.flush()

    if not mt5.initialize():
        print(f"ERRO: Falha ao inicializar MT5: {mt5.last_error()}")
        sys.exit(1)

    symbols = mt5.symbols_get()
    if symbols is None or len(symbols) == 0:
        print("ERRO: Nenhum símbolo retornado pelo MT5")
        mt5.shutdown()
        sys.exit(1)

    total_symbols = len(symbols)
    symbols_to_process = list(symbols[:limit]) if limit > 0 else list(symbols)
    num_to_process = len(symbols_to_process)

    print(f"Total de símbolos no MT5: {total_symbols}")
    print(f"Processando nesta rodada: {num_to_process} {'(TESTE CONTROLADO)' if limit > 0 else '(RODADA COMPLETA)'}\n")
    sys.stdout.flush()

    # --- FASE A ---
    phase_a_results, summary = run_phase_a(symbols_to_process, num_to_process)

    # --- FASE B (opcional: somente se lista explícita passada) ---
    phase_b_results = []
    if phase_b_symbols:
        phase_b_results = run_phase_b_for_candidates(phase_b_symbols)

    mt5.shutdown()

    elapsed_total = round(time.time() - start_total_time, 2)
    summary["total_symbols"] = total_symbols
    summary["elapsed_seconds"] = elapsed_total

    print("\n==================================================")
    print("CATALOG INSPECTION SUMMARY (FASE A — PROBE)")
    print("==================================================")
    print(f"total_symbols       : {summary['total_symbols']}")
    print(f"processed           : {summary['processed']}")
    print(f"d1_probe_ok         : {summary['d1_probe_ok']}")
    print(f"no_d1_history       : {summary['no_d1_history']}")
    print(f"inactive            : {summary['inactive']}")
    print(f"errors              : {summary['errors']}")
    print(f"elapsed_seconds     : {elapsed_total}s")
    print("\nCategorias:")
    for c, count in summary["categories"].items():
        print(f"  {c:<8}: {count}")
    print("==================================================")
    sys.stdout.flush()

    # Salva resultados
    output = {"summary": summary, "phase_a": phase_a_results, "phase_b": phase_b_results}
    with open("scratch/catalog_inspection_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print("\nResultados salvos em scratch/catalog_inspection_results.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspeção em Duas Fases do Catálogo MT5")
    parser.add_argument("--limit", type=int, default=0, help="Limita símbolos para teste controlado")
    parser.add_argument("--phase-b", nargs="*", default=None, help="Símbolos para busca completa na Fase B")
    args = parser.parse_args()
    inspect_catalog(limit=args.limit, phase_b_symbols=args.phase_b)
