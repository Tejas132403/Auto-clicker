@echo off
title Stop All King Phones
cd /d "%~dp0"
call py.cmd king_stop.py
echo.
pause
