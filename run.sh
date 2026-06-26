#!/bin/bash
# Quick start script for Bank Nifty Wick Closing Principle Backtester

echo "================================"
echo "Bank Nifty Wick Closing Principle"
echo "Backtester - Setup & Run"
echo "================================"
echo ""

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "✗ Python is not installed. Please install Python 3.7+"
    exit 1
fi

echo "✓ Python found: $(python --version)"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -q yfinance pandas numpy

if [ $? -ne 0 ]; then
    echo "✗ Failed to install dependencies"
    exit 1
fi

echo "✓ Dependencies installed"
echo ""

# Run the backtester
echo "Starting backtest..."
echo ""
python wick_closing_backtest.py

echo ""
echo "================================"
echo "Backtest Complete!"
echo "Check CSV files for trade logs"
echo "================================"
