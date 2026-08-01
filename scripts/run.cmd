@echo off
REM Configura la key y publica (setup + opencode run) en un solo comando.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
exit /b %errorlevel%
