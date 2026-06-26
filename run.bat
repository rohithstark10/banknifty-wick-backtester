@echo off
REM Quick start script for Bank Nifty Wick Closing Principle Backtester (Windows)

echo ================================
echo Bank Nifty Wick Closing Principle
echo Backtester - Setup ^& Run
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python is not installed. Please install Python 3.7+
    exit /b 1
)

echo OK Python found: 
for /f "tokens=*" %%i in ('python --version') do echo %%i
echo.

REM Install dependencies
echo Installing dependencies...
pip install -q yfinance pandas numpy

if errorlevel 1 (
    echo X Failed to install dependencies
    exit /b 1
)

echo OK Dependencies installed
echo.

REM Run the backtester
echo Starting backtest...
echo.
python wick_closing_backtest.py

echo.
echo ================================
echo Backtest Complete!
echo Check CSV files for trade logs
echo ================================
pause
