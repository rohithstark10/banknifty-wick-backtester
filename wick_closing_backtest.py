"""
═══════════════════════════════════════════════════════════════════
  WICK CLOSING PRINCIPLE — Bank Nifty Backtester
  Timeframes : 5-min and 15-min candles
  Capital    : ₹50,000  |  Max Risk/Trade: 10% = ₹5,000
  EMAs used  : 55, 89, 144
═══════════════════════════════════════════════════════════════════

HOW TO GET BANK NIFTY DATA (free options):
  Option A – yfinance:
      pip install yfinance pandas numpy
      symbol = "^NSEBANK"   # Bank Nifty index

  Option B – Zerodha Kite API / Upstox / AngelOne:
      Download 5-min / 15-min OHLCV CSV and pass the path below.

  The script auto-detects whether you pass a symbol (yfinance)
  or a CSV path.
═══════════════════════════════════════════════════════════════════
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
#  CONFIGURATION — edit these
# ─────────────────────────────────────────────
CAPITAL          = 50_000          # Total capital (₹)
RISK_PER_TRADE   = 0.10            # 10% of capital = ₹5,000 max risk
BROKERAGE        = 20              # ₹20 per order (Zerodha flat fee)
SLIPPAGE_PCT     = 0.05 / 100     # 0.05% slippage per leg
LOT_SIZE         = 15              # Bank Nifty lot size (current)
WEEKS_BACKTEST   = 8               # Last 8 weeks

# EMA periods (Wick Closing Principle uses 55/89/144)
EMA_PERIODS      = [55, 89, 144]
TREND_EMA        = 55              # Primary trend filter

# Wick ratio: wick must be >= this fraction of total candle range
MIN_WICK_RATIO   = 0.40            # 40% of H-L must be wick

# Stop-loss: candle's extreme wick tip
# Take-profit: 2× risk (RR 1:2)
RR_RATIO         = 2.0

DATA_SOURCE      = "^NSEBANK"      # yfinance symbol  OR  "path/to/file.csv"
TIMEFRAMES       = ["5m", "15m"]   # yfinance interval strings

# ─────────────────────────────────────────────
#  DATA LOADER
# ─────────────────────────────────────────────
def load_data(source: str, interval: str) -> pd.DataFrame:
    """Load OHLCV data from yfinance or CSV."""
    if source.endswith(".csv"):
        df = pd.read_csv(source, parse_dates=["datetime"], index_col="datetime")
        df.columns = [c.capitalize() for c in df.columns]
    else:
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("Run: pip install yfinance")

        import datetime as dt
        end   = dt.datetime.now()
        start = end - dt.timedelta(weeks=WEEKS_BACKTEST)
        ticker = yf.Ticker(source)
        df = ticker.history(start=start, end=end, interval=interval)
        df.index = df.index.tz_localize(None) if df.index.tzinfo else df.index
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    # Keep only market hours: 9:15 – 15:30 IST
    if hasattr(df.index, 'time'):
        df = df.between_time("09:15", "15:25")

    return df


# ─────────────────────────────────────────────
#  INDICATOR CALCULATIONS
# ─────────────────────────────────────────────
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add EMAs and wick measurements."""
    df = df.copy()

    for p in EMA_PERIODS:
        df[f"EMA_{p}"] = df["Close"].ewm(span=p, adjust=False).mean()

    # Candle anatomy
    df["body_top"]    = df[["Open", "Close"]].max(axis=1)
    df["body_bot"]    = df[["Open", "Close"]].min(axis=1)
    df["body_size"]   = df["body_top"] - df["body_bot"]
    df["upper_wick"]  = df["High"] - df["body_top"]
    df["lower_wick"]  = df["body_bot"] - df["Low"]
    df["candle_range"]= df["High"] - df["Low"]
    df["upper_ratio"] = np.where(df["candle_range"] > 0,
                                 df["upper_wick"] / df["candle_range"], 0)
    df["lower_ratio"] = np.where(df["candle_range"] > 0,
                                 df["lower_wick"] / df["candle_range"], 0)

    # Trend: price vs primary EMA
    df["trend_up"]   = df["Close"] > df[f"EMA_{TREND_EMA}"]
    df["trend_down"]  = df["Close"] < df[f"EMA_{TREND_EMA}"]

    # Is any EMA in proximity? (within 0.3% of High or Low)
    ema_cols = [f"EMA_{p}" for p in EMA_PERIODS]
    df["near_ema_high"] = (
        df[ema_cols].apply(lambda col: (df["High"] - col).abs() / df["High"] < 0.003)
                    .any(axis=1)
    )
    df["near_ema_low"] = (
        df[ema_cols].apply(lambda col: (df["Low"] - col).abs() / df["Low"] < 0.003)
                    .any(axis=1)
    )

    return df


# ─────────────────────────────────────────────
#  SIGNAL GENERATION (4 scenarios)
# ─────────────────────────────────────────────
def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scenario 1 & 3 — SHORT signals (uptrend + upper wick rejection)
    Scenario 2 & 4 — LONG  signals (downtrend + lower wick reclaim)
    """
    df = df.copy()

    # ── SHORT signals ──────────────────────────────────────────
    # Candle wicked above key level / EMA and CLOSED back below it
    # = bearish wick rejection in an uptrend
    sc1_short = (
        df["trend_up"] &
        (df["upper_ratio"] >= MIN_WICK_RATIO) &
        (df["Close"] < df["body_top"])           # closed lower than open (red candle helpful)
    )

    # Scenario 3: wick touched 55/89/144 EMA zone from above
    sc3_short = (
        df["trend_up"] &
        df["near_ema_high"] &
        (df["upper_ratio"] >= MIN_WICK_RATIO)
    )

    df["signal_short"] = (sc1_short | sc3_short).astype(int)

    # ── LONG signals ───────────────────────────────────────────
    # Candle wicked below key level / EMA and CLOSED back above it
    # = bullish wick reclaim in a downtrend
    sc2_long = (
        df["trend_down"] &
        (df["lower_ratio"] >= MIN_WICK_RATIO) &
        (df["Close"] > df["body_bot"])
    )

    sc4_long = (
        df["trend_down"] &
        df["near_ema_low"] &
        (df["lower_ratio"] >= MIN_WICK_RATIO)
    )

    df["signal_long"] = (sc2_long | sc4_long).astype(int)

    return df


# ─────────────────────────────────────────────
#  POSITION SIZING
# ─────────────────────────────────────────────
def calc_lots(entry: float, stop: float) -> int:
    """
    Number of lots so risk ≤ 10% of capital.
    Risk per lot = |entry - stop| × LOT_SIZE
    """
    max_risk  = CAPITAL * RISK_PER_TRADE
    risk_pts  = abs(entry - stop)
    if risk_pts == 0:
        return 0
    risk_per_lot = risk_pts * LOT_SIZE
    lots = int(max_risk // risk_per_lot)
    return max(lots, 0)


# ─────────────────────────────────────────────
#  TRADE SIMULATOR
# ─────────────────────────────────────────────
def simulate_trades(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bar-by-bar simulation.
    Entry : next candle open after signal
    Stop  : wick tip of signal candle
    Target: entry ± (stop distance × RR_RATIO)
    Exit  : first bar where High/Low breaches target or stop
    """
    trades = []
    n = len(df)

    i = 0
    while i < n - 1:
        row = df.iloc[i]

        for direction in ["long", "short"]:
            if row[f"signal_{direction}"] != 1:
                continue

            # Entry on next bar's open
            entry_idx = i + 1
            if entry_idx >= n:
                break

            entry_row  = df.iloc[entry_idx]
            entry_price = entry_row["Open"] * (1 + SLIPPAGE_PCT if direction == "long"
                                               else 1 - SLIPPAGE_PCT)

            # Stop = wick tip of signal candle
            if direction == "long":
                stop_price  = row["Low"]
                target_price = entry_price + (entry_price - stop_price) * RR_RATIO
            else:
                stop_price  = row["High"]
                target_price = entry_price - (stop_price - entry_price) * RR_RATIO

            lots = calc_lots(entry_price, stop_price)
            if lots == 0:
                continue

            # Scan forward for exit
            exit_price  = None
            exit_reason = "EOD"
            exit_idx    = entry_idx

            # Don't hold overnight — exit at 15:15 same day
            entry_date = df.index[entry_idx].date()

            for j in range(entry_idx + 1, min(entry_idx + 100, n)):
                future = df.iloc[j]
                if future.name.date() != entry_date:
                    # EOD exit at previous close
                    exit_price  = df.iloc[j - 1]["Close"]
                    exit_reason = "EOD"
                    exit_idx    = j - 1
                    break

                if direction == "long":
                    if future["Low"] <= stop_price:
                        exit_price  = stop_price
                        exit_reason = "SL"
                        exit_idx    = j
                        break
                    if future["High"] >= target_price:
                        exit_price  = target_price
                        exit_reason = "TP"
                        exit_idx    = j
                        break
                else:
                    if future["High"] >= stop_price:
                        exit_price  = stop_price
                        exit_reason = "SL"
                        exit_idx    = j
                        break
                    if future["Low"] <= target_price:
                        exit_price  = target_price
                        exit_reason = "TP"
                        exit_idx    = j
                        break

            if exit_price is None:
                exit_price  = df.iloc[min(entry_idx + 99, n - 1)]["Close"]
                exit_reason = "EOD"
                exit_idx    = min(entry_idx + 99, n - 1)

            # P&L calculation
            if direction == "long":
                gross_pnl = (exit_price - entry_price) * lots * LOT_SIZE
            else:
                gross_pnl = (entry_price - exit_price) * lots * LOT_SIZE

            net_pnl = gross_pnl - (2 * BROKERAGE)   # entry + exit brokerage

            trades.append({
                "entry_time"  : df.index[entry_idx],
                "exit_time"   : df.index[exit_idx],
                "direction"   : direction.upper(),
                "entry_price" : round(entry_price, 2),
                "stop_price"  : round(stop_price, 2),
                "target_price": round(target_price, 2),
                "exit_price"  : round(exit_price, 2),
                "lots"        : lots,
                "exit_reason" : exit_reason,
                "gross_pnl"   : round(gross_pnl, 2),
                "net_pnl"     : round(net_pnl, 2),
            })

        i += 1

    return pd.DataFrame(trades)


# ─────────────────────────────────────────────
#  PERFORMANCE METRICS
# ─────────────────────────────────────────────
def performance_report(trades: pd.DataFrame, tf: str) -> dict:
    if trades.empty:
        print(f"\n[{tf}] No trades found. Try adjusting MIN_WICK_RATIO.")
        return {}

    wins  = trades[trades["net_pnl"] > 0]
    losses= trades[trades["net_pnl"] <= 0]

    total_pnl   = trades["net_pnl"].sum()
    win_rate    = len(wins) / len(trades) * 100
    avg_win     = wins["net_pnl"].mean()   if not wins.empty   else 0
    avg_loss    = losses["net_pnl"].mean() if not losses.empty else 0
    profit_factor = (wins["net_pnl"].sum() / abs(losses["net_pnl"].sum())
                     if not losses.empty else float("inf"))

    # Drawdown
    cumulative  = trades["net_pnl"].cumsum()
    rolling_max = cumulative.cummax()
    drawdown    = (cumulative - rolling_max)
    max_dd      = drawdown.min()

    # Expectancy per trade
    expectancy  = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)

    by_direction = trades.groupby("direction")["net_pnl"].agg(["sum","count","mean"])
    by_exit      = trades.groupby("exit_reason")["net_pnl"].agg(["count","sum"])

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  WICK CLOSING PRINCIPLE — Bank Nifty  [{tf}]
╚══════════════════════════════════════════════════════════╝
  Capital          : ₹{CAPITAL:,.0f}
  Max Risk/Trade   : ₹{CAPITAL * RISK_PER_TRADE:,.0f}  ({RISK_PER_TRADE*100:.0f}%)

  ── Overview ───────────────────────────────────────────
  Total Trades     : {len(trades)}
  Winning Trades   : {len(wins)}  ({win_rate:.1f}%)
  Losing Trades    : {len(losses)}
  Net P&L          : ₹{total_pnl:,.2f}
  Return on Capital: {total_pnl/CAPITAL*100:.2f}%

  ── Risk / Reward ──────────────────────────────────────
  Avg Win          : ₹{avg_win:,.2f}
  Avg Loss         : ₹{avg_loss:,.2f}
  Profit Factor    : {profit_factor:.2f}
  Expectancy/Trade : ₹{expectancy:,.2f}
  Max Drawdown     : ₹{max_dd:,.2f}  ({max_dd/CAPITAL*100:.2f}%)

  ── By Direction ───────────────────────────────────────
{by_direction.to_string()}

  ── By Exit Reason ─────────────────────────────────────
{by_exit.to_string()}
""")

    return {
        "timeframe"    : tf,
        "trades"       : len(trades),
        "win_rate"     : round(win_rate, 2),
        "net_pnl"      : round(total_pnl, 2),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown" : round(max_dd, 2),
        "expectancy"   : round(expectancy, 2),
    }


def save_trade_log(trades: pd.DataFrame, tf: str):
    out_path = f"banknifty_wick_{tf.replace('m','min')}_trades.csv"
    trades.to_csv(out_path, index=False)
    print(f"  Trade log saved → {out_path}")


# ─────────────────────────────────────────────
#  SENSITIVITY ANALYSIS
# ─────────────────────────────────────────────
def sensitivity_sweep(df_raw: pd.DataFrame, tf: str):
    """
    Sweep key parameters and show how Net P&L changes.
    Key variables: MIN_WICK_RATIO, RR_RATIO, TREND_EMA
    """
    print(f"\n{'═'*58}")
    print(f"  SENSITIVITY SWEEP [{tf}]")
    print(f"{'═'*58}")

    results = []
    for wick_r in [0.30, 0.40, 0.50, 0.60]:
        for rr in [1.5, 2.0, 2.5, 3.0]:
            for t_ema in [55, 89, 144]:
                # Re-run pipeline with modified params
                df2 = df_raw.copy()
                for p in EMA_PERIODS:
                    df2[f"EMA_{p}"] = df2["Close"].ewm(span=p, adjust=False).mean()

                df2["body_top"]    = df2[["Open","Close"]].max(axis=1)
                df2["body_bot"]    = df2[["Open","Close"]].min(axis=1)
                df2["upper_wick"]  = df2["High"] - df2["body_top"]
                df2["lower_wick"]  = df2["body_bot"] - df2["Low"]
                df2["candle_range"]= df2["High"] - df2["Low"]
                df2["upper_ratio"] = np.where(df2["candle_range"]>0,
                                              df2["upper_wick"]/df2["candle_range"],0)
                df2["lower_ratio"] = np.where(df2["candle_range"]>0,
                                              df2["lower_wick"]/df2["candle_range"],0)
                df2["trend_up"]    = df2["Close"] > df2[f"EMA_{t_ema}"]
                df2["trend_down"]  = df2["Close"] < df2[f"EMA_{t_ema}"]

                ema_cols = [f"EMA_{p}" for p in EMA_PERIODS]
                df2["near_ema_high"] = df2[ema_cols].apply(
                    lambda col: (df2["High"]-col).abs()/df2["High"] < 0.003).any(axis=1)
                df2["near_ema_low"]  = df2[ema_cols].apply(
                    lambda col: (df2["Low"]-col).abs()/df2["Low"] < 0.003).any(axis=1)

                sc1 = df2["trend_up"]  & (df2["upper_ratio"] >= wick_r)
                sc3 = df2["trend_up"]  & df2["near_ema_high"] & (df2["upper_ratio"] >= wick_r)
                sc2 = df2["trend_down"]& (df2["lower_ratio"] >= wick_r)
                sc4 = df2["trend_down"]& df2["near_ema_low"]  & (df2["lower_ratio"] >= wick_r)
                df2["signal_short"] = (sc1|sc3).astype(int)
                df2["signal_long"]  = (sc2|sc4).astype(int)

                # Minimal trade sim
                pnl_list = []
                n = len(df2)
                for i in range(n-1):
                    row = df2.iloc[i]
                    for direction in ["long","short"]:
                        if row[f"signal_{direction}"] != 1: continue
                        ei = i + 1
                        if ei >= n: break
                        er = df2.iloc[ei]
                        ep = er["Open"]
                        sp = row["Low"] if direction=="long" else row["High"]
                        tp = ep + (ep-sp)*rr if direction=="long" else ep - (sp-ep)*rr
                        lots = calc_lots(ep, sp)
                        if lots == 0: continue
                        ed = df2.index[ei].date()
                        exp = ep
                        for j in range(ei+1, min(ei+100,n)):
                            fut = df2.iloc[j]
                            if fut.name.date() != ed: exp=df2.iloc[j-1]["Close"]; break
                            if direction=="long":
                                if fut["Low"]<=sp:  exp=sp;  break
                                if fut["High"]>=tp: exp=tp; break
                            else:
                                if fut["High"]>=sp: exp=sp;  break
                                if fut["Low"]<=tp:  exp=tp; break
                        g = (exp-ep)*lots*LOT_SIZE if direction=="long" else (ep-exp)*lots*LOT_SIZE
                        pnl_list.append(g - 2*BROKERAGE)

                if pnl_list:
                    results.append({
                        "wick_ratio": wick_r,
                        "rr"        : rr,
                        "trend_ema" : t_ema,
                        "trades"    : len(pnl_list),
                        "net_pnl"   : round(sum(pnl_list), 0),
                        "win_rate"  : round(sum(1 for p in pnl_list if p>0)/len(pnl_list)*100, 1),
                    })

    sens_df = pd.DataFrame(results).sort_values("net_pnl", ascending=False)
    print("\n  Top 10 parameter combinations by Net P&L:")
    print(sens_df.head(10).to_string(index=False))

    print("\n  ── Sensitivity by Variable ──")
    print("  Wick Ratio impact on Net P&L (avg):")
    print(sens_df.groupby("wick_ratio")["net_pnl"].mean().round(0).to_string())
    print("\n  RR Ratio impact on Net P&L (avg):")
    print(sens_df.groupby("rr")["net_pnl"].mean().round(0).to_string())
    print("\n  Trend EMA impact on Net P&L (avg):")
    print(sens_df.groupby("trend_ema")["net_pnl"].mean().round(0).to_string())

    sens_df.to_csv(f"sensitivity_{tf.replace('m','min')}.csv", index=False)
    print(f"\n  Full sensitivity table saved → sensitivity_{tf.replace('m','min')}.csv")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def run_backtest(source: str = DATA_SOURCE):
    all_summary = []

    for tf in TIMEFRAMES:
        print(f"\n{'═'*58}")
        print(f"  Loading Bank Nifty data ��� {tf} candles …")
        print(f"{'═'*58}")

        try:
            df_raw = load_data(source, tf)
        except Exception as e:
            print(f"  ✗ Could not load data for {tf}: {e}")
            continue

        print(f"  Loaded {len(df_raw):,} candles  |  "
              f"{df_raw.index[0].date()} → {df_raw.index[-1].date()}")

        df = add_indicators(df_raw)
        df = generate_signals(df)

        long_signals  = df["signal_long"].sum()
        short_signals = df["signal_short"].sum()
        print(f"  Signals — LONG: {long_signals}  |  SHORT: {short_signals}")

        trades = simulate_trades(df)
        metrics = performance_report(trades, tf)

        if not trades.empty:
            save_trade_log(trades, tf)
            all_summary.append(metrics)

        # Sensitivity sweep
        sensitivity_sweep(df_raw, tf)

    # ── Comparative summary ─────────────────────
    if len(all_summary) > 1:
        print(f"\n{'═'*58}")
        print("  COMPARATIVE SUMMARY")
        print(f"{'═'*58}")
        print(pd.DataFrame(all_summary).to_string(index=False))


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else DATA_SOURCE
    run_backtest(source)
