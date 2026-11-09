@echo off
REM Запуск без сборки exe
cd /d "%~dp0"
py -3 -m pip install --upgrade -r requirements.txt
start "" pyw -3 main.py
