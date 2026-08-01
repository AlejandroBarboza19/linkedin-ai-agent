@echo off
REM Configura la key y abre opencode en modo interactivo (setup + TUI) en un solo comando.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
exit /b %errorlevel%
