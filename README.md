# Bank Nifty Wick Closing Principle Backtester

## Overview
A sophisticated backtesting engine for the **Wick Closing Principle** trading strategy on Bank Nifty (NSE India's banking index) futures.

**Strategy**: Detects wick rejection/reclaim patterns in 5-min and 15-min timeframes using EMA-based trend filters and position sizing based on risk management.

## Features
- ✅ Multi-timeframe analysis (5-min, 15-min)
- ✅ Risk-based position sizing (max 10% risk per trade)
- ✅ EOD position exit (no overnight holds)
- ✅ 4 trading scenarios (long/short + wick rejection/reclaim)
- ✅ Performance metrics (win rate, profit factor, max drawdown, expectancy)
- ✅ Sensitivity analysis (parameter sweep)
- ✅ Trade-by-trade CSV logs

## Installation

```bash
# Clone the repository
git clone https://github.com/rohithstark10/banknifty-wick-backtester.git
cd banknifty-wick-backtester

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

### Option 1: Backtest with yfinance (auto-downloads Bank Nifty data)
```bash
python wick_closing_backtest.py
```

### Option 2: Backtest with your own CSV
```bash
python wick_closing_backtest.py path/to/banknifty_5min.csv
```

CSV format: columns must include `datetime`, `Open`, `High`, `Low`, `Close`, `Volume`

## Configuration
Edit these parameters in `wick_closing_backtest.py`:

```python
CAPITAL          = 50_000          # Trading capital (₹)
RISK_PER_TRADE   = 0.10            # 10% of capital = ₹5,000 max loss
BROKERAGE        = 20              # ₹20 per order (Zerodha flat)
LOT_SIZE         = 15              # Bank Nifty lot size
WEEKS_BACKTEST   = 8               # Lookback period

MIN_WICK_RATIO   = 0.40            # Wick must be 40% of candle range
RR_RATIO         = 2.0             # Risk:Reward 1:2
TREND_EMA        = 55              # Trend filter EMA period
```

## Output

After running, you'll get:

1. **Console Report**: Win rate, P&L, profit factor, max drawdown
2. **Trade Logs** (CSV files):
   - `banknifty_wick_5min_trades.csv`
   - `banknifty_wick_15min_trades.csv`
3. **Sensitivity Analysis** (CSV files):
   - `sensitivity_5min.csv`
   - `sensitivity_15min.csv`

## Example Output

```
╔══════════════════════════════════════════════════════════╗
║  WICK CLOSING PRINCIPLE — Bank Nifty  [5m]
╚══════════════════════════════════════════════════════════╝
  Capital          : ₹50,000
  Max Risk/Trade   : ₹5,000  (10%)

  ── Overview ───────────────────────────────────────────
  Total Trades     : 42
  Winning Trades   : 28  (66.7%)
  Losing Trades    : 14
  Net P&L          : ₹18,540.00
  Return on Capital: 37.08%

  ── Risk / Reward ──────────────────────────────────────
  Avg Win          : ₹1,050.00
  Avg Loss         : ₹-650.00
  Profit Factor    : 1.85
  Expectancy/Trade : ₹441.43
  Max Drawdown     : ₹-2,150.00  (-4.30%)
```

## Strategy Logic

### 4 Scenarios:
1. **Scenario 1**: Uptrend + Upper wick rejection (SHORT)
2. **Scenario 2**: Downtrend + Lower wick reclaim (LONG)
3. **Scenario 3**: Uptrend + Wick touches EMA zone (SHORT)
4. **Scenario 4**: Downtrend + Wick touches EMA zone (LONG)

### Entry & Exit:
- **Entry**: Next candle's open (after signal candle)
- **Stop-Loss**: Wick tip of signal candle
- **Target**: Entry ± (SL distance × RR ratio)
- **Exit Rules**:
  - Hit target → Take Profit (TP)
  - Hit stop → Stop Loss (SL)
  - Same-day close → End of Day (EOD)

## Key Metrics

| Metric | Meaning |
|--------|----------|
| **Win Rate** | % of winning trades (50%+ is acceptable) |
| **Profit Factor** | Gross wins ÷ Gross losses (>1.5 is good) |
| **Expectancy** | Average P&L per trade (should be positive) |
| **Max Drawdown** | Worst peak-to-trough loss (should be <10% of capital) |

## Disclaimer

⚠️ **This backtester is for educational purposes only.**
- Past performance ≠ future results
- Always validate on live paper trading first
- Use appropriate position sizing for your risk tolerance
- Bank Nifty futures require ≥ ₹1L margin with broker

## Supported Data Sources

1. **yfinance** (free, auto-downloaded): `^NSEBANK`
2. **Zerodha Kite API** (export CSV)
3. **Upstox** (export CSV)
4. **AngelOne** (export CSV)
5. **Any OHLCV CSV** with datetime index

## License
MIT License

## Author
[@rohithstark10](https://github.com/rohithstark10)
