@echo off
:: ============================================================
::  run_overlay.bat — Launch the Voice Overlay
:: ============================================================
:: Uses pythonw to avoid showing a console window.
:: The overlay runs as a tiny floating microphone button.
:: ============================================================

cd /d "%~dp0"
pythonw main.py --overlay
