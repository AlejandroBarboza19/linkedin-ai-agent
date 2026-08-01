@echo off
REM Solo configura la key: lee .env y escribe .opencode/zai-key (no publica).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
exit /b %errorlevel%
